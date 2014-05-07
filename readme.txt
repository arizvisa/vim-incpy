Incremental Python -- Incpy

Synopsis:
This allows one to incrementally develop python code, similar to Emacs' SLIME. Essentially you can select/hilight any python code, execute it, and store the output to a window. It kind of allows you to rapidly prototype code within vim as opposed to prototyping at the commandline or via another tool.

Usage:
Simply get used to doing window management and visual mode. When hilighting some text, hit '!' (bang) to execute currently selected code. This will execute it through python, and output will be captured in a window.

    V (visual-mode)
    ! (execute-python)

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

Some commands have been added to vim that can be used to remap Incpy's functionality to your own.
    PyRange (Execute the currently selected range)
    Py <python-code> (Execute the specified python code)
    PyHelp <python-object> (Call help on the specified python object)
    PyLine (Execute the current line)
    PyBuffer (Execute the entire buffer)

Configuration:
Incpy has 4 options that are set via global variables. These should be set in your .vimrc. If any of these options are not set upon plugin initialization, reasonable defaults will be chosen.

    let g:PyBufferName = "pythonwindoworsomething"
    let g:PyBufferPlacement = "below" | "above"
    let g:PyBufferSize = "10"
    let g:PyEnableHide = 0
    let g:PyHideDelay = integer
    let g:PyNewLine = integer

Installation:
Python2 support in vim (+python) is required in order to use this. Check :version or run vim with -v to see. This plugin has been tested with vim 7.0.

    To install locally simply copy to your vim runtimepath.
    $ cp -R */ ~/.vim

    To install globally, simply copy to everybody's runtimepath
    $ cp -R */ $VIMINSTALLDIR/vimfiles

To see your runtime path, you can simply execute the following at vim's commandline.
    :set runtimepath
