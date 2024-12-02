" Based on an idea that bniemczyk@gmail.com had during some conversation.
" Thanks to ccliver@gmail.org for his input on this.
" Thanks to Tim Pope <vimNOSPAM@tpope.info> for pointing out preview windows.
"
" This plugin requires vim to be compiled w/ python support. It came into
" existance when I noticed that most of my earlier Python development
" consisted of copying code into the python interpreter in order to check
" my results or to test out some code.
"
" After developing this insight, I decided to make vim more friendly for
" that style of development by writing an interface around interaction
" with Vim's embedded instance of python. Pretty soon I recognized that
" it'd be nice if all my programs could write their output into a buffer
" and so I worked on refactoring all of the code so that it would capture
" stdout and stderr from an external program and update a buffer.
"
" This is the result of these endeavors. I apologize in the advance for the
" hackiness as this plugin was initially written when I was first learning
" Python.
"
" When a .py file is opened (determined by filetype), a buffer is created.
" Any output from the target program is then written into this buffer.
"
" This buffer has the default name of "Scratch" which will contain the
" output of all of the code that you've executed using this plugin. By
" default, this buffer is shown in a split-screened window.
"
" Usage:
" Move the cursor to a line or highlight some text in visual mode.
" Once you hit "!", the selected text or line will then be fed into into
" the target application's stdin. Any output that the target program
" emits will then be updated in the "Scratch" buffer.
"
" Mappings:
" !              -- execute line at the current cursor position
" <C-/> or <C-\> -- display `repr()` for symbol at cursor using `g:incpy#EvalFormat`.
" <C-S-@>        -- display `help()` for symbol at cursor using `g:incpy#HelpFormat`.
"
" Installation:
" Simply copy the root of this repository into your user's runtime directory.
" If in a posixy environment, this is at "$HOME/.vim".
" If in windows, this is at "$USERPROFILE/vimfiles".
"
" This repository contains two directories, one of which is "plugin" and the
" second of which is "python". The "plugin" directory contains this file and
" will determine the runtime directory that it was installed in. This will
" then locate the "python" directory which contains the python code that this
" plugin depends on.
"
" Window Management:
" Proper usage of this plugin requires basic knowledge of window management
" in order to use it effectively. Some mappings that can be used to manage
" windows in vim are as follows.
"
"   <C-w>s -- horizontal split
"   <C-w>v -- vertical split
"   <C-w>o -- hide all other windows
"   <C-w>q -- close current window
"   <C-w>{h,l,j,k} -- move to the window left,right,down,up from current one
"
" Configuration:
" To configure this plugin, one can simply set some globals in their ".vimrc"
" file. The available options are as follows.
"
" string g:incpy#Program      -- name of subprogram (if empty, use vim's internal python).
" bool   g:incpy#OutputFollow -- flag that specifies to tail the output of the subprogram.
" any    g:incpy#InputStrip   -- when executing input, specify whether to strip leading indentation.
" bool   g:incpy#Echo         -- when executing input, echo it to the "Scratch" buffer.
" string g:incpy#HelpFormat   -- the formatspec to use when getting help on an expression.
" string g:incpy#EchoNewline  -- the formatspec to emit when done executing input.
" string g:incpy#EchoFormat   -- the formatspec for each line of code being emitted.
" string g:incpy#EvalFormat   -- the formatspec to evaluate and emit an expression with.
" any    g:incpy#EvalStrip    -- describes how to strip input before being evaluated
" string g:incpy#ExecFormat   -- the formatspec to execute an expression with.
" string g:incpy#ExecStrip    -- describes how to strip input before being executed
"
" string g:incpy#WindowName     -- the name of the output buffer. defaults to "Scratch".
" dict   g:incpy#WindowOptions  -- the options to use when creating the output window.
" bool   g:incpy#WindowPreview  -- whether to use preview windows for the program output.
" float  g:incpy#WindowRatio    -- the ratio of the window size when creating it
" bool   g:incpy#WindowStartup  -- show the window as soon as the plugin is started.
" string g:incpy#WindowPosition -- the position at which to create the window. can be
"                                  either "above", "below", "left", or "right".
" string g:incpy#PythonStartup  -- the name of the dotfile to seed python's globals with.
"
" bool   g:incpy#Terminal   -- whether to use the terminal api for external interpreters.
" bool   g:incpy#Greenlets  -- whether to use greenlets for external interpreters.
"
" string g:incpy#PluginName     -- the internal name of the plugin, used during logging.
" string g:incpy#PackageName    -- the internal package name, found in sys.modules.
"
" Todo:
" - When the filetype of the current buffer was specified, the target output buffer
"   used to pop-up. This used to be pretty cool, but was deprecated. It'd be neat
"   to bring this back somehow.
" - When outputting the result of something that was executed, it might be possible
"   to create a fold (`zf`). This would also be pretty cool so that users can hide
"   something that they were just testing.
" - It might be change the way some of the wrappers around the interface works so
"   that a user can attach a program to a particular buffer from their ".vimrc"
"   instead of starting up with a default one immediately attached. This way
"   mappings can be customized as well.
" - If would be pretty cool if an output buffer could be attached to an editing
"   buffer so that management of multiple program buffers would be local to
"   whatever the user is currently editing.

if exists("g:loaded_incpy") && g:loaded_incpy
    finish
endif
let g:loaded_incpy = v:true

" Add a virtual package with the specified name referencing the given path.
function! incpy#SetupPythonLoader(package, currentscriptpath)
    let l:slashes = substitute(a:currentscriptpath, "\\", "/", "g")

    " Look up from our current script's directory for a python sub-directory
    let python_dir = finddir("python", printf("%s;", l:slashes))
    if isdirectory(python_dir)
        call incpy#SetupPackageLoader(a:package, python_dir)
        return
    endif

    throw printf("Unable to determine basepath from script %s", l:slashes)
endfunction

function! incpy#SetupPythonInterpreter(package)

    " If greenlets were specified, then make it visible by importing `gevent
    " into the current python environment via sys.modules.
    if g:incpy#Greenlets
        pythonx __import__('gevent')

    " Otherwise, we only need to warn the user about using it if they're
    " trying to run an external program without having the terminal api.
    elseif len(g:incpy#Program) > 0 && !(has('terminal') || has('nvim'))
        echohl WarningMsg | echomsg printf('WARNING:%s:Using plugin to run an external program without support for greenlets could be unstable', g:incpy#PluginName) | echohl None
    endif

    " Now we can setup the interpreter and its view.
    call incpy#SetupInterpreter(a:package)
    call incpy#SetupInterpreterView(a:package)

endfunction

"" Entry point
function! incpy#LoadPlugin()
    let s:current_script=expand("<sfile>:p:h")

    call incpy#SetupOptions()
    call incpy#SetupPythonLoader(g:incpy#PackageName, s:current_script)
    call incpy#SetupPythonInterpreter(g:incpy#PackageName)
    call incpy#SetupCommands()
    call incpy#SetupKeys()

    " if we've been told to create a window on startup, then show the
    " window when the "VimEnter" autocmd event has been triggered.
    autocmd VimEnter * if g:incpy#WindowStartup | call incpy#Show() | endif

    " if we're using an external program, then we can just ignore the dotfile
    " since it really only makes sense when using the python interpreter.
    if g:incpy#Program == ""
        call incpy#ImportDotfile()
    endif

    " if greenlets were specifed then make sure to update them during cursor movement
    if g:incpy#Greenlets
        autocmd CursorHold * pythonx __import__('gevent').idle(0.0)
        autocmd CursorHoldI * pythonx __import__('gevent').idle(0.0)
        autocmd CursorMoved * pythonx __import__('gevent').idle(0.0)
        autocmd CursorMovedI * pythonx __import__('gevent').idle(0.0)
    endif
endfunction

" Now we can attempt to load the plugin...if python is available.
if has("python") || has("python3")
    call incpy#LoadPlugin()

" Otherwise we need to complain about the lack of python.
else
    call incpy#SetupOptions()
    echohl ErrorMsg | echomsg printf("ERROR:%s:Vim compiled without +python support. Unable to initialize plugin from %s", g:incpy#PluginName, expand("<sfile>")) | echohl None
endif
