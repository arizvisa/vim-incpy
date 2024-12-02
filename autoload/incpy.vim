""" Public interface and management

" Check to see if a python site-user dotfile exists in the users home-directory.
function! incpy#ImportDotfile()
    let l:dotfile = g:incpy#PythonStartup
    if filereadable(l:dotfile)
        call incpy#interpreter#execute_file(l:dotfile)
    endif
endfunction

" Execute the specified lines within the current interpreter.
function! incpy#Range(begin, end)
    return incpy#interpreter#range(a:begin, a:end)
endfunction

" Start the target program and attach it to a buffer
function! incpy#Start()
    return incpy#interpreter#start()
endfunction

" Stop the target program and detach it from its buffer
function! incpy#Stop()
    return incpy#interpreter#stop()
endfunction

" Restart the target program by stopping and starting it
function! incpy#Restart()
    return incpy#interpreter#restart()
endfunction

function! incpy#Show()
    return incpy#interpreter#show()
endfunction

function! incpy#Hide()
    return incpy#interpreter#hide()
endfunction

""" Plugin interaction interface
function! incpy#Execute(line)
    return incpy#interpreter#execute(a:line)
endfunction

function! incpy#ExecuteRaw(line)
    return incpy#interpreter#execute_raw(a:line)
endfunction

function! incpy#ExecuteRange() range
    return incpy#interpreter#execute_range()
endfunction

function! incpy#ExecuteBlock() range
    return incpy#interpreter#execute_block()
endfunction

function! incpy#ExecuteSelected() range
    return incpy#interpreter#execute_selected()
endfunction

function! incpy#Evaluate(expr)
    return incpy#interpreter#evaluate(a:expr)
endfunction

function! incpy#EvaluateRange() range
    return incpy#interpreter#evaluate_range()
endfunction

function! incpy#EvaluateBlock() range
    return incpy#interpreter#evaluate_block()
endfunction

function! incpy#EvaluateSelected() range
    return incpy#interpreter#evaluate_selected()
endfunction

function! incpy#Halp(expr)
    return incpy#interpreter#halp(a:expr)
endfunction

function! incpy#HalpSelected() range
    return incpy#interpreter#halp_selected()
endfunction

function! incpy#ExecuteFile(filename)
    return incpy#interpreter#execute_file(a:filename)
endfunction

""" Internal interface for setting up the plugin loader and packages
function! incpy#SetupPackageLoader(package, path)
    return incpy#internal#load(a:package, a:path)
endfunction

"" Setting up the interpreter and its view
function! incpy#SetupInterpreter(package)
    return incpy#internal#setup(a:package)
endfunction

function! incpy#SetupInterpreterView(package)
    return incpy#internal#setup_view(a:package)
endfunction

""" Plugin options and setup for keybindings and commands
function! incpy#SetupOptions()
    return incpy#options#setup()
endfunction

function! incpy#SetupCommands()
    return incpy#bindings#commands()
endfunction

function! incpy#SetupKeys()
    return incpy#bindings#setup()
endfunction
