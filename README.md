# incpy.vim

This allows one to incrementally develop python code, similar to
Emacs' SLIME. Essentially you can select/highlight any python code,
execute it, and store the output to a window. It kind of allows
you to rapidly prototype code within vim, as its being developed,
as opposed to testing it at the command line or by submitting it
to another interpreter.

Despite the name of this plugin highlighting that it focuses on
python, there is support for using any program where its output
can be captured. The program to use as an interpreter can be
specified with a global variable that contains the path to the
desired executable or a specific python interpreter. If one is
not specified, the internal python interpreter that comes with
vim will be used.

If your instance of vim has been compiled with support for the
`+terminal` feature, the terminal-based interpreter will be
selected by default.

Support has also been added to use any external program and capture
its output into a buffer. This can be specified via a global variable
which contains the path to the executable or a python executable.
If one is not specified, vim's internal python will be used.

## Usage

### Mappings

Simply get used to doing window management and visual mode.
When highlighting some text, hit '!' (bang) to execute currently selected
code. This will execute it through python, and output will be captured
in a window.

    v or V      (visual-mode or visual-mode-linewise)
    !           (execute-python)
    C-/ or C-\  (display repr for symbol under cursor)
    C-@         (display help for symbol under cursor)

### Commands

Some commands have been added to vim that can be used to remap vim-incpy
functionality to your own.

    :Py <python-code> (Execute the specified python code)

    :PyLine (execute the current line)
    :PyBuffer (execute the entire buffer)
    :PyRange (execute the currently selected range)

    :PyEval <expression>     (evaluate the specified expression)
    :PyEvalRange             (evaluate the currently selected code)
    :PyHelp <python-object>  (call help on the specified symbol)
    :PyHelpRange             (call help on the currently selected code)

### Window Management

Some shortcut keys if you're new to window-management.

    C-w (window-mode prefix)
    C-w s (split)
    C-w q (close-window)
    C-w v (vertical split)
    C-w o (only; close other windows)

    5C-w - (shrink window height by 5)
    5C-w + (increase window height by 5)
    5C-w < (shrink window width by 5)
    5C-w > (increase window width by 5)
    5C-w _ (set window height to 5)

    C-w h (go to the window left of current)
    C-w l (go to the window right of current)
    C-w j (go one window down)
    C-w k (go one window up)

## Installation

This plugin requires vim to be compiled with python support which can be
checked by looking for the `+python` or the `+python3/dyn` features in the
output of `:version`. This plugin has been tested with vim 9.1.

The plugin is currently hosted on GitHub at https://github.com/arizvisa/vim-incpy.
Please use GitHub for reporting any issues or feature requests.

### Installation - Plugin manager

To install using a plugin manager, add the line corresponding to your
package manager to your `.vimrc`.

    " Vundle
    call vundle#begin()
    Plugin 'arizvisa/vim-incpy'
    ...

    " Dein
    call dein#begin(...)
    call dein#add('arizvisa/vim-incpy')
    ...

    " Neobundle
    call neobundle#begin(...)
    NeoBundleFetch 'arizvisa/vim-incpy'

### Installation - Packages

To install using Vim, clone the repository into your file system at the
correct `runtimepath` so that Vim's `:packadd` (from `Packages`) will find
it.

    # if in a posix environment
    $ git clone https://github.com/arizvisa/vim-incpy ~/.vim/pack/some-name/opt/vim-incpy

    # if in a windows-y environment
    $ git clone https://github.com/arizvisa/vim-incpy $USERPROFILE/vimfiles/pack/some-name/opt/vim-incpy

Afterwards, you can then use `:packadd` from `Packages` in your `.vimrc`
to add it.

    packadd 'vim-incpy'

You might also need to run `:helptags` to generate the tags for the
documentation. Please review the help for more details.

### Installation - Directly

Simply copy the root of this repository into your user's runtime directory.
If in a posix-y environment, this is at "`$HOME/.vim`". If in windows, this
is at "`$USERPROFILE/vimfiles`".

    # Local user installation
    $ cp -R */ ~/.vim

    # Global installation
    $ cp -R */ $VIMINSTALLDIR/vimfiles

To see your runtime path, you can simply execute the following at vim's
command line.

    :set runtimepath

### Installation - Directories

This repository contains three directories, "`plugin`", "`autoload`",
and "`python`". The "`plugin`" directory contains the logic for loading
the plugin and setting up the default options. The "`autoload`" directory
contains functionality used for executing code within the plugin, and the
"`python`" directory contains the python code that the plugin depends on.
Documentation that can be indexed with `:helptags` can also be found in
"`doc/incpy.txt`".

## Configuration

vim-incpy has a couple options that can be set via global variables. These should
be set in your `.vimrc`. If any of these options are not set upon plugin
initialization, reasonable defaults will be chosen. The full list of options
are available at `:help incpy-configuration`. For customizing the output
window, the following options are available.

    bool   g:incpy#WindowPreview  ——  whether to use preview windows for the program output.
    string g:incpy#WindowName     —— the name of the output buffer. defaults to "Scratch".
    bool   g:incpy#WindowFixed    —— refuse to allow automatic resizing of the window.
    dict   g:incpy#WindowOptions  —— the options to use when creating the output window.
    float  g:incpy#WindowRatio    —— the ratio of the window size when creating it
    bool   g:incpy#WindowStartup  —— show the window as soon as the plugin is started.
    string g:incpy#WindowPosition —— the position at which to create the window. can be
                                     either "above", "below", "left", or "right".
    string g:incpy#PythonStartup  —— the name of the dotfile to seed python's globals with.

For configuring an external program, the following globals are available.

    string g:incpy#Program      —— name of subprogram (if empty, use vim's internal python).
    bool   g:incpy#OutputFollow —— flag that specifies to tail the output of the subprogram.
    any    g:incpy#InputStrip   —— when executing input, specify whether to strip leading indentation.
    bool   g:incpy#Echo         —— when executing input, echo it to the "Scratch" buffer.
    string g:incpy#HelpFormat   —— the formatspec to use when getting help on an expression.
    string g:incpy#EchoNewline  —— the formatspec to emit when done executing input.
    string g:incpy#EchoFormat   —— the formatspec for each line of code being emitted.
    string g:incpy#EvalFormat   —— the formatspec to evaluate and emit an expression with.
    any    g:incpy#EvalStrip    —— describes how to strip input before being evaluated
    string g:incpy#ExecFormat   —— the formatspec to execute an expression with.
    string g:incpy#ExecStrip    —— describes how to strip input before being executed

### Example Configuration

The following example configuration can be used for an external python
interpreter. Normally the internal python interpreter should be enough,
but if you're running your python interpreter remotely, this might be
useful.

    let g:incpy#Name = "python-output"                (name of output-buffer)
    let g:incpy#Program = "" | "/path/to/executable"  (path to python executable, uses vim's internal python if not defined)
    let g:incpy#ProgramEcho = 1                       (echo all input sent to program)
    let g:incpy#ProgramFollow = 1                     (follow all output in buffer, like tail -f)
    let g:incpy#ProgramStrip = 1                      (strip any leading indent before executing)

    let g:incpy#WindowPosition = "below" | "above" | "left" | "right"
    let g:incpy#WindowRatio = 1.0/8             (window size as a percentage of current view)
    let g:incpy#WindowPreview = 0               (use vim's preview windows for output window)
    let g:incpy#WindowOptions = {}              (any custom options to add to window)
    let g:incpy#WindowFixed = 0                 (fix the windows position so that vim won't auto-resize the window)

For more examples, please review the help for the plugin via `:help incpy`.

## About

This plugin requires vim to be compiled w/ python support. It came into
existence when I noticed that most of my earlier Python development
consisted of copying code into the python interpreter in order to check
my results or to test out some ideas.

After developing this insight, I decided to make vim more friendly for
that style of development by writing an interface around interaction
with Vim's embedded instance of python. Pretty soon I recognized that
it'd be nice if all my programs could write their output into a buffer
and so I worked on refactoring all of the code so that it would capture
`stdout` and `stderr` from an external program and update a buffer.

This is the result of these endeavors. I apologize in the advance for the
hackiness as this plugin was initially written when I was first learning
Python.

### Credits

* Based on an idea that bniemczyk@gmail.com and I had during some conversation.
* Thanks to ccliver@gmail.org for his input on this.
* Thanks to Tim Pope <vimNOSPAM@tpope.info> for pointing out preview windows.
