""" Public interface for management of the interpreter.

" Start the configured interpreter and attach it to a buffer.
function! incpy#interpreter#start()
    call incpy#internal#execute(g:incpy#PackageName, 'start', [])
endfunction

" Stop the running interpreter and detach it from its buffer.
function! incpy#interpreter#stop()
    call incpy#internal#execute(g:incpy#PackageName, 'stop', [])
endfunction

" Restart the configured interpreter by stopping and starting it.
function! incpy#interpreter#restart()
    for method in ['stop', 'start']
        call incpy#internal#execute(g:incpy#PackageName, method, [])
    endfor
endfunction

" Show the currently running interpreter.
function! incpy#interpreter#show()
    let parameters = map(['incpy#WindowPosition', 'incpy#WindowRatio'], 'incpy#python#global_variable(v:val)')
    call incpy#internal#execute_guarded(g:incpy#PackageName, ['show'], parameters, incpy#options#window())
endfunction

" Hide the currently running interpreter.
function! incpy#interpreter#hide()
    call incpy#internal#execute_guarded(g:incpy#PackageName, ['hide'], [])
endfunction

""" Plugin interface for interacting with the interpreter.

" Execute the lines in the specified range within the current intterpreter.
function! incpy#interpreter#range(begin, end)
    let lines = getline(a:begin, a:end)
    let input_stripped = incpy#string#strip(g:incpy#InputStrip, lines)

    " Verify that the input returned is a type that we support
    if index([v:t_string, v:t_list], type(input_stripped)) < 0
        throw printf("Unable to process the given input due to it being of an unsupported type (%s): %s", typename(input_stripped), input_stripped)
    endif

    " Strip our input prior to its execution, then check its result type
    " to ensure that we can pass to the interpreter without issue.
    let code_stripped = incpy#string#strip(g:incpy#ExecStrip, input_stripped)
    if !(type(code_stripped) == v:t_string || type(code_stripped) == v:t_list)
        throw printf("Unable to execute due to an unknown input type (%s) being returned by %s: %s", typename(code_stripped), 'g:incpy#ExecStrip', code_stripped)
    endif

    " Show the window and then send each line to the interpreter. If any of the
    " lines are empty, then avoid sending that specific line.
    call incpy#internal#execute_guarded(g:incpy#PackageName, ['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 'incpy#python#global_variable(v:val)'), incpy#options#window())
    let l:commands_stripped = (type(code_stripped) == v:t_list)? code_stripped : [code_stripped]
    for command_stripped in l:commands_stripped
        if len(command_stripped) > 0
            call incpy#internal#communicate(g:incpy#PackageName, incpy#string#singleline(g:incpy#ExecFormat, "\"\\"), command_stripped)
        endif
    endfor

    " If the user configured us to follow the output, then do as we were told.
    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

" Execute the specified line within the current interpreter.
function! incpy#interpreter#execute(line)
    let input_stripped = incpy#string#strip(g:incpy#InputStrip, a:line)
    if index([v:t_string, v:t_list], type(input_stripped)) < 0
        throw printf("Unable to process the given input due to it being of an unsupported type (%s): %s", typename(input_stripped), input_stripped)
    endif

    " Now we need to strip our input for execution.
    let code_stripped = incpy#string#strip(g:incpy#ExecStrip, input_stripped)
    if !(type(code_stripped) == v:t_string || type(code_stripped) == v:t_list)
        throw printf("Unable to execute due to an unknown input type (%s) being returned by %s: %s", typename(code_stripped), 'g:incpy#ExecStrip', code_stripped)
    endif

    " Show the window and send each line from our input to the interpreter. If
    " the stripped code results in an empty string, then skip over the sending.
    call incpy#internal#execute_guarded(g:incpy#PackageName, ['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 'incpy#python#global_variable(v:val)'), incpy#options#window())
    let l:commands_stripped = (type(code_stripped) == v:t_list)? code_stripped : [code_stripped]
    for command_stripped in l:commands_stripped
        if len(command_stripped) > 0
            call incpy#internal#communicate(g:incpy#PackageName, incpy#string#singleline(g:incpy#ExecFormat, "\"\\"), command_stripped)
        endif
    endfor

    " If the user configured us to follow the output, then do as we were told.
    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

" Execute a line of code within the current interpreter without any encoding,
" stripping, or formatting.
function! incpy#interpreter#execute_raw(line)
    call incpy#internal#execute_guarded(g:incpy#PackageName, ['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 'incpy#python#global_variable(v:val)'), incpy#options#window())
    call incpy#internal#communicate(g:incpy#PackageName, "{}", a:line)
    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

" Evaluate the expression a:expr within the current interpreter.
function! incpy#interpreter#evaluate(expr)
    let stripped = incpy#string#strip(g:incpy#EvalStrip, a:expr)

    " Evaluate an expression in the target using the plugin. If the stripped
    " expression is an empty string (or list), then there's nothing to do.
    if len(stripped) > 0
        call incpy#internal#execute_guarded(g:incpy#PackageName, ['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 'incpy#python#global_variable(v:val)'), incpy#options#window())
        call incpy#internal#communicate(g:incpy#PackageName, incpy#string#singleline(g:incpy#EvalFormat, "\"\\"), stripped)
    endif

    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

" Use the current interpreter to print out the help for the given expression.
function! incpy#interpreter#halp(expr)
    let LetMeSeeYouStripped = substitute(a:expr, '^[ \t\n]\+\|[ \t\n]\+$', '', 'g')

    " Execute g:incpy#HelpFormat in the target using the plugin's cached communicator
    if len(LetMeSeeYouStripped) > 0
        call incpy#internal#execute_guarded(g:incpy#PackageName, ['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 'incpy#python#global_variable(v:val)'), incpy#options#window())
        call incpy#internal#communicate(g:incpy#PackageName, incpy#string#singleline(g:incpy#HelpFormat, "\"\\"), incpy#string#escape_double(LetMeSeeYouStripped))
    endif
endfunction

" Execute the contents of the specified file within the current interpreter.
function! incpy#interpreter#execute_file(filename)
    let open_and_execute = printf("with open(%s) as infile: exec(infile.read())", incpy#string#quote_double(a:filename))
    call incpy#internal#execute(g:incpy#PackageName, 'communicate', [incpy#string#quote_single(open_and_execute), 'silent=True'])
endfunction

""" Wrappers that depend on the functions above.
function! incpy#interpreter#execute_range() range
    return incpy#interpreter#range(a:firstline, a:lastline)
endfunction

function! incpy#interpreter#execute_block() range
    let l:block = incpy#ui#selection#block()
    throw printf('Block range execution is currently not implemented')
endfunction

function! incpy#interpreter#execute_selected() range
    let l:block = incpy#ui#selection#current()
    throw printf('Selection range execution is currently not implemented')
endfunction

function! incpy#interpreter#evaluate_range() range
    return incpy#interpreter#evaluate(join(incpy#ui#selection#range()))
endfunction

function! incpy#interpreter#evaluate_block() range
    return incpy#interpreter#evaluate(join(incpy#ui#selection#block()))
endfunction

function! incpy#interpreter#evaluate_selected() range
    return incpy#interpreter#evaluate(join(incpy#ui#selection#current()))
endfunction

function! incpy#interpreter#halp_selected() range
    return incpy#interpreter#halp(join(incpy#ui#selection#current()))
endfunction
