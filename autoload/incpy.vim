""" Public interface and management

" Execute the specified lines within the current interpreter.
function! incpy#Range(begin, end)
    return incpy#python#Range(a:begin, a:end)
endfunction

" Start the target program and attach it to a buffer
function! incpy#Start()
    return incpy#python#Start()
endfunction

" Stop the target program and detach it from its buffer
function! incpy#Stop()
    return incpy#python#Stop()
endfunction

" Restart the target program by stopping and starting it
function! incpy#Restart()
    return incpy#python#Restart()
endfunction

function! incpy#Show()
    return incpy#python#Show()
endfunction

function! incpy#Hide()
    return incpy#python#Hide()
endfunction

""" Plugin interaction interface
function! incpy#Execute(line)
    return incpy#python#Execute(a:line)
endfunction

function! incpy#ExecuteRaw(line)
    return incpy#python#ExecuteRaw(a:line)
endfunction

function! incpy#ExecuteRange() range
    return incpy#Range(a:firstline, a:lastline)
endfunction

function! incpy#ExecuteBlock() range
    let l:block = incpy#ui#selection#block()
    throw printf('Block range execution is currently not implemented')
endfunction

function! incpy#ExecuteSelected() range
    let l:block = incpy#ui#selection#current()
    throw printf('Selection range execution is currently not implemented')
endfunction

function! incpy#Evaluate(expr)
    return incpy#python#Evaluate(a:expr)
endfunction

function! incpy#EvaluateRange() range
    return incpy#Evaluate(join(incpy#ui#selection#range()))
endfunction

function! incpy#EvaluateBlock() range
    return incpy#Evaluate(join(incpy#ui#selection#block()))
endfunction

function! incpy#EvaluateSelected() range
    return incpy#Evaluate(join(incpy#ui#selection#current()))
endfunction

function! incpy#Halp(expr)
    return incpy#python#Halp(a:expr)
endfunction

function! incpy#HalpSelected() range
    return incpy#Halp(join(incpy#ui#selection#current()))
endfunction

function! incpy#ExecuteFile(filename)
    return incpy#python#ExecuteFile(a:filename)
endfunction

""" Internal interface for setting up the plugin loader and packages
function! incpy#SetupPackageLoader(package, path)
    return incpy#python#load_package(a:package, a:path)
endfunction

"" Setting up the interpreter and its view
function! incpy#SetupInterpreter(package)
    return incpy#python#setup(a:package)
endfunction

function! incpy#SetupInterpreterView(package)
    return incpy#python#setup_view(a:package)
endfunction
