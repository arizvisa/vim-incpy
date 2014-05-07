Incremental Python -- Incpy

Synopsis:
This allows one to incrementally develop python code, similar to Emacs' SLIME. Essentially you can select/hilight any python code, execute it, and store the output to a window. It kind of allows you to rapidly prototype code within vim as opposed to prototyping at the commandline or via another tool.

Recently support has been added to use any program and capture it's output into a buffer. This can be specified via a global variable which contains the path to the executable, or python executable. If one is not specified, vim's internal python will be used.

Usage:
Simply get used to doing window management and visual mode. When hilighting some text, hit '!' (bang) to execute currently selected code. This will execute it through python, and output will be captured in a window.

    V (visual-mode)
    ! (execute-python)
    C-@ (display repr for symbol under cursor)
    C-_ (display help for symbol under cursor)

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

    C-w h (go to the window left of current)
    C-w l (go to the window right of current)
    C-w j (go one window down)
    C-w k (go one window up)

Some commands have been added to vim that can be used to remap Incpy's functionality to your own.
    :Py <python-code> (Execute the specified python code)

    :PyLine (execute the current line)
    :PyBuffer (execute the entire buffer)
    :PyRange (execute the currently selected range)

    :PyEval <python-object>  (evaluate the specified symbol)
    :PyEvalRange             (evaluate the currently selected code)
    :PyHelp <python-object>  (call help on the specified symbol)
    :PyHelpRange             (call help on the currently selected code)

Configuration:
Incpy has a couple options that are set via global variables. These should be set in your .vimrc. If any of these options are not set upon plugin initialization, reasonable defaults will be chosen.

    let g:incpy#Name = "python-output"                (name of output-buffer)
    let g:incpy#Program = "" | "/path/to/executable"  (path to python executable, uses vim's internal python if not defined)
    let g:incpy#ProgramEcho = 1                       (echo all input sent to program)
    let g:incpy#ProgramFollow = 1                     (follow all output in buffer, like tail -f)
    let g:incpy#ProgramStrip = 1                      (strip any leading indent before executing)
    
    let g:incpy#WindowPosition = "below" | "above" | "left" | "right"
    let g:incpy#WindowRatio = 1.0/8             (window size as a percentage of current view)
    let g:incpy#WindowPreview = 0               (use vim's preview windows for output window)
    let g:incpy#WindowOptions = {}              (any custom options to add to window)

Installation:
Python2 support in vim (+python) is required in order to use this. Check :version or run vim with -v to see. This plugin has been tested with vim 7.0.

    To install locally simply copy to your vim runtimepath.
    $ cp -R */ ~/.vim

    To install globally, simply copy to everybody's runtimepath
    $ cp -R */ $VIMINSTALLDIR/vimfiles

To see your runtime path, you can simply execute the following at vim's commandline.
    :set runtimepath
