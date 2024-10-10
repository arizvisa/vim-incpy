""" Utilities for dealing with visual-mode selection
function! s:selected() range
    " really, vim? really??
    let oldvalue = getreg("")
    normal gvy
    let result = getreg("")
    call setreg("", oldvalue)
    return split(result, '\n')
endfunction

function! s:selected_range() range
    let [l:left, l:right] = [getcharpos("'<"), getcharpos("'>")]
    let [l:lline, l:rline] = [l:left[1], l:right[1]]
    let [l:lchar, l:rchar] = [l:left[2], l:right[2]]

    if l:lline < l:rline
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = [l:lchar, l:rchar]
    elseif l:lline > l:rline
        let [l:minline, l:maxline] = [l:rline, l:lline]
        let [l:minchar, l:maxchar] = [l:rchar, l:lchar]
    else
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = sort([l:lchar, l:rchar], 'N')
    endif

    let lines = getline(l:minline, l:maxline)
    if len(lines) > 2
        let selection = [strcharpart(lines[0], l:minchar - 1)] + slice(lines, 1, -1) + [strcharpart(lines[-1], 0, l:maxchar)]
    elseif len(lines) > 1
        let selection = [strcharpart(lines[0], l:minchar - 1)] + [strcharpart(lines[-1], 0, l:maxchar)]
    else
        let selection = [strcharpart(lines[0], l:minchar - 1, 1 + l:maxchar - l:minchar)]
    endif
    return selection
endfunction

function! s:selected_block() range
    let [l:left, l:right] = [getcharpos("'<"), getcharpos("'>")]
    let [l:lline, l:rline] = [l:left[1], l:right[1]]
    let [l:lchar, l:rchar] = [l:left[2], l:right[2]]

    if l:lline < l:rline
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = [l:lchar, l:rchar]
    elseif l:lline > l:rline
        let [l:minline, l:maxline] = [l:rline, l:lline]
        let [l:minchar, l:maxchar] = [l:rchar, l:lchar]
    else
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = sort([l:lchar, l:rchar], 'N')
    endif

    let lines = getline(l:minline, l:maxline)
    let selection = map(lines, 'strcharpart(v:val, l:minchar - 1, 1 + l:maxchar - l:minchar)')
    return selection
endfunction

""" Utilities for window management
function! s:windowselect(id)

    " check if we were given a bunk window id
    if a:id == -1
        throw printf("Invalid window identifier %d", a:id)
    endif

    " select the requested window id, return the previous window id
    let current = winnr()
    execute printf("%d wincmd w", a:id)
    return current
endfunction

function! s:windowtail(bufid)

    " if we were given a bunk buffer id, then we need to bitch
    " because we can't select it or anything
    if a:bufid == -1
        throw printf("Invalid buffer identifier %d", a:bufid)
    endif

    " tail the window that's using the specified buffer id
    let last = s:windowselect(bufwinnr(a:bufid))
    if winnr() == bufwinnr(a:bufid)
        keepjumps noautocmd normal gg
        keepjumps noautocmd normal G
        call s:windowselect(last)

    " check which tabs the buffer is in
    else
        call s:windowselect(last)

        let tc = tabpagenr()
        for tn in range(tabpagenr('$'))
            if index(tabpagebuflist(1 + tn), a:bufid) > -1
                execute printf("tabnext %d", tn)
                let tl = s:windowselect(bufwinnr(a:bufid))
                keepjumps noautocmd normal gg
                keepjumps noautocmd normal G
                call s:windowselect(tl)
            endif
        endfor
        execute printf("tabnext %d", tc)
    endif
endfunction

function! s:striplist_by_option(option, lines)
    let items = a:lines

    " Strip the fetched lines if the user configured us to
    if type(a:option) == v:t_bool
        let result = a:option == v:true? map(items, "trim(v:val)") : items

    " If the type is a string, then use it as a regex that
    elseif type(a:option) == v:t_string
        let result = map(items, a:option)

    " Otherwise it's a function to use as a transformation
    elseif type(a:option) == v:t_func
        let F = a:option
        let result = F(items)

    " Anything else is an unsupported filtering option.
    else
        throw printf("Unable to strip lines using an unknown filtering option (%s): %s", typename(a:option), a:option)
    endif

    return result
endfunction

function! s:stripstring_by_option(option, string)
    if type(a:option) == v:t_bool
        let result = a:option == v:true? trim(a:string) : a:string

    elseif type(a:option) == v:t_string
        let expression = a:option
        let results = map([a:string], expression)
        let result = results[0]

    elseif type(a:option) == v:t_func
        let F = a:option
        let result = F(a:string)

    else
        throw printf("Unable to strip string due to an unknown filtering option (%s): %s", typename(a:option), a:option)
    endif
    return result
endfunction

function! s:strip_by_option(option, input)
    if type(a:input) == v:t_list
        let result = s:striplist_by_option(a:option, a:input)
    elseif type(a:input) == v:t_string
        let result = s:stripstring_by_option(a:option, a:input)
    else
        throw printf("Unknown parameter type: %s", type(a:input))
    endif
    return result
endfunction

""" Utilities for escaping strings and such
function! s:escape_single(string)
    return escape(a:string, '''\')
endfunction

function! s:escape_double(string)
    return escape(a:string, '"\')
endfunction

function! s:quote_single(string)
    return printf("'%s'", escape(a:string, '''\'))
endfunction

function! s:quote_double(string)
    return printf("\"%s\"", escape(a:string, '"\'))
endfunction

" escape the multiline string with the specified characters and return it as a single-line string
function! s:singleline(string, escape)
    let escaped = escape(a:string, a:escape)
    let result = substitute(escaped, "\n", "\\\\n", "g")
    return result
endfunction

" convert from a vim native type to a string that can be interpreted by python
function! s:render_native_as_python(object)
    let object_type = type(a:object)
    if object_type == v:t_number
        return printf('%d', a:object)
    elseif object_type == v:t_string
        return s:quote_single(a:object)
    elseif object_type is v:null
        return 'None'
    elseif object_type == v:t_float
        return printf('%f', a:object)
    elseif object_type == v:t_bool
        return a:object? 'True' : 'False'
    elseif object_type == v:t_blob
        let items = []
        for by in a:object
            let items += [printf("%#04x", by)]
        endfor
        return printf('bytearray([%s])', join(items, ','))
    else
        throw printf("Unable to render the specified type (%d): %s", object_type, a:object)
    endif
endfunction

" convert from a vim type (container or native) to a string that can be interpreted by python
function! s:render_as_python(object)
    let object_type = type(a:object)
    if object_type == v:t_list
        let items = map(a:object, 's:render_as_python(v:val)')
        return printf('[%s]', join(items, ','))
    elseif object_type == v:t_dict
        let rendered = map(a:object, 'printf("%s:%s", s:render_as_python(v:key), s:render_as_python(v:val))')
        let items = map(keys(rendered), 'get(rendered, v:val)')
        return printf('{%s}', join(items, ','))
    else
        return s:render_native_as_python(a:object)
    endif
endfunction

""" Utilities related to executing python
function! s:execute_python_in_workspace(package, command)
    let l:multiline_command = split(a:command, "\n")
    let l:workspace_module = join([a:package, 'workspace'], '.')

    " Guard whatever it is we were asked to execute by
    " ensuring that our module workspace has been loaded.
    execute printf("pythonx __builtins__.__import__(%s).exec_", s:quote_single(a:package))
    execute printf("pythonx __builtins__.__import__(%s)", s:quote_single(l:workspace_module))

    " If our command contains 3x single or double-quotes, then
    " we format our strings with the one that isn't used.
    if stridx(a:command, '"""') < 0
        let strings = printf("%s\n%s\n%s", 'r"""', join(l:multiline_command, "\n"), '"""')
    else
        let strings = printf("%s\n%s\n%s", "r'''", join(l:multiline_command, "\n"), "'''")
    endif

    " Now we need to render our multilined list of commands to
    " a multilined string, and then execute it in our workspace.
    let l:python_execute = join(['__builtins__', printf("__import__(%s)", s:quote_single(a:package)), 'exec_'], '.')
    let l:python_workspace = join(['__builtins__', printf("__import__(%s)", s:quote_single(l:workspace_module)), 'workspace', '__dict__'], '.')

    execute printf("pythonx (lambda F, ns: (lambda s: F(s, ns, ns)))(%s, %s)(%s)", l:python_execute, l:python_workspace, strings)
endfunction

function! s:execute_interpreter_cache(method, parameters, keywords={})
    let l:cache = [printf('__import__(%s)', s:quote_single(g:incpy#PackageName)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    let l:kwparameters = len(a:keywords)? [printf('**%s', s:render_as_python(a:keywords))] : []
    call s:execute_python_in_workspace(g:incpy#PackageName, printf('%s(%s)', join(l:cache + l:method, '.'), join(a:parameters + l:kwparameters, ', ')))
endfunction

function! s:execute_interpreter_cache_guarded(method, parameters, keywords={})
    let l:cache = [printf('__import__(%s)', s:quote_single(g:incpy#PackageName)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    let l:kwparameters = len(a:keywords)? [printf('**%s', s:render_as_python(a:keywords))] : []
    call s:execute_python_in_workspace(g:incpy#PackageName, printf("hasattr(%s, %s) and %s(%s)", join(slice(l:cache, 0, -1), '.'), s:quote_single(l:cache[-1]), join(l:cache + l:method, '.'), join(a:parameters + l:kwparameters, ', ')))
endfunction

function! s:communicate_interpreter_encoded(format, code)
    let l:cache = [printf('__import__(%s)', s:quote_single(g:incpy#PackageName)), 'cache']
    let l:encoded = substitute(a:code, '.', '\=printf("\\x%02x", char2nr(submatch(0)))', 'g')
    let l:lambda = printf("(lambda interpreter: (lambda code: interpreter.communicate(code)))(%s)", join(cache, '.'))
    execute printf("pythonx %s(\"%s\".format(\"%s\"))", l:lambda, a:format, l:encoded)
endfunction

" Just a utility for generating a python expression that accesses a vim global variable
function! s:generate_gvar_expression(name)
    let interface = [printf('__import__(%s)', s:quote_single(join([g:incpy#PackageName, 'interface'], '.'))), 'interface']
    let gvars = ['vim', 'gvars']
    return printf("%s[%s]", join(interface + gvars, '.'), s:quote_double(a:name))
endfunction

""" Dynamically generated python code used during setup
function! s:generate_package_loader_function(name)

    " Generate a closure that we will use to update the meta_path.
    let unnamed_definition =<< trim EOF
    def %s(package_name, package_path, plugin_name):
        import builtins, os, sys, six

        # Create a namespace that we will execute our loader.py
        # script in. This is so we can treat it as a module.
        class workspace: pass
        loader = workspace()
        loader.path = os.path.join(package_path, 'loader.py')

        with builtins.open(loader.path, 'rt') as infile:
            six.exec_(infile.read(), loader.__dict__, loader.__dict__)

        # These are our types that are independent of the python version.
        integer_types = tuple({type(sys.maxsize + n) for n in range(2)})
        string_types = tuple({type(s) for s in ['', u'']})
        text_types = tuple({t.__base__ for t in string_types}) if sys.version_info.major < 3 else string_types
        ordinal_types = (string_types, bytes)

        version_independent_types = {
            'integer_types': integer_types,
            'string_types': string_types,
            'text_types': text_types,
            'ordinal_types': ordinal_types,
        }

        # Populate the namespace that will be used by the fake package
        # that will be generated by our instantiated meta_path object.
        namespace = {name : value for name, value in version_independent_types.items()}
        namespace['reraise'] = six.reraise
        namespace['exec_'] = six.exec_

        # Initialize a logger and assign it to our package.
        import logging
        namespace['logger'] = logging.basicConfig() or logging.getLogger(plugin_name)

        # Now we can instantiate a meta_path object that creates a
        # package containing the contents of the path we were given.
        files = [filename for filename in os.listdir(package_path) if filename.endswith('.py')]
        iterable = ((os.path.splitext(filename), os.path.join(package_path, filename)) for filename in files)
        submodules = {name : path for (name, ext), path in iterable}
        pythonx_finder = loader.vim_plugin_support_finder(package_path, submodules)

        # Then we do another to expose a temporary workspace
        # that we can use to load code and other things into.
        workspace_finder = loader.workspace_finder(workspace=loader)

        # Now we can return a packager that wraps both finders.
        yield loader.vim_plugin_packager(package_name, [pythonx_finder, workspace_finder], namespace)
    EOF

    return printf(join(unnamed_definition, "\n"), a:name)
endfunction

function! s:generate_interpreter_cache_snippet(package)

    let install_interpreter =<< trim EOC
        __import__, package_name = __builtins__['__import__'], %s
        package = __import__(package_name)
        interface, interpreters = (getattr(__import__('.'.join([package.__name__, module])), module) for module in ['interface', 'interpreters'])

        # grab the program specified by the user
        program = interface.vim.gvars["incpy#Program"]
        use_terminal = any(interface.vim.has(feature) for feature in ['terminal', 'nvim']) and interface.vim.gvars["incpy#Terminal"]

        # figure out which interpreter to use and then instantiate it.
        try:
            if len(program) > 0 and use_terminal:
                interpreter = interpreters.neoterminal if interface.vim.has('nvim') else interpreters.terminal
            elif len(program) > 0:
                interpreter = interpreters.external
            else:
                interpreter = interpreters.internal
            cache = interpreter(*[program] if program else [])

        # if we couldn't start the interpreter, then fall back to an internal one
        except Exception:
            hasattr(package, 'logger') and package.logger.fatal("error starting external interpreter: {:s}".format(program), exc_info=True)
            hasattr(package, 'logger') and package.logger.warning("falling back to internal python interpreter")
            cache = interpreters.internal()

        # assign the interpreter object into our package
        cache.start(interface.vim.gvars["incpy#WindowName"])
        package.cache = cache
    EOC

    return printf(join(install_interpreter, "\n"), s:quote_single(a:package))
endfunction

function! s:generate_interpreter_view_snippet(package)

    let create_view =<< trim EOC
        __import__, package_name = __builtins__['__import__'], %s
        package = __import__(package_name)
        [interface] = (getattr(__import__('.'.join([package.__name__, module])), module) for module in ['interface'])

        # grab the cached interpreter out of the package
        cache = package.cache

        # now we just need to store its buffer id
        interface.vim.gvars['incpy#BufferId'] = cache.view.buffer.number
    EOC

    return printf(join(create_view, "\n"), s:quote_single(a:package))
endfunction

function! s:get_window_options(other={})
    let core = g:incpy#CoreWindowOptions

    " Initialize our result dictionary with the core window options.
    let result = {}
    for o in keys(core)
        let result[o] = core[o]
    endfor

    " Specially handle the window preview option.
    if exists('g:incpy#WindowPreview')
        let result['preview'] = g:incpy#WindowPreview
    endif

    " If the user wants the window to be fixed, then set the correct options.
    if exists('g:incpy#WindowFixed') && g:incpy#WindowFixed
        let result['winfixwidth'] = v:true
        let result['winfixheight'] = v:true
    endif

    " Merge any of the other options that we were given
    for o in keys(a:other)
        let result[o] = a:other[o]
    endfor
    return result
endfunction

""" Public interface and management

" Execute the specified lines within the current interpreter.
function! incpy#Range(begin, end)
    let lines = getline(a:begin, a:end)
    let input_stripped = s:strip_by_option(g:incpy#InputStrip, lines)

    " Verify that the input returned is a type that we support
    if index([v:t_string, v:t_list], type(input_stripped)) < 0
        throw printf("Unable to process the given input due to it being of an unsupported type (%s): %s", typename(input_stripped), input_stripped)
    endif

    " Strip our input prior to its execution.
    let code_stripped = s:strip_by_option(g:incpy#ExecStrip, input_stripped)
    call s:execute_interpreter_cache_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())

    " If it's not a list or a string, then we don't support it.
    if !(type(code_stripped) == v:t_string || type(code_stripped) == v:t_list)
        throw printf("Unable to execute due to an unknown input type (%s): %s", typename(code_stripped), code_stripped)
    endif

    " If we've got a string, then execute it as a single line.
    let l:commands_stripped = (type(code_stripped) == v:t_list)? code_stripped : [code_stripped]
    for command_stripped in l:commands_stripped
        call s:communicate_interpreter_encoded(s:singleline(g:incpy#ExecFormat, "\"\\"), command_stripped)
    endfor

    " If the user configured us to follow the output, then do as we were told.
    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

" Start the target program and attach it to a buffer
function! incpy#Start()
    call s:execute_interpreter_cache('start', [])
endfunction

" Stop the target program and detach it from its buffer
function! incpy#Stop()
    call s:execute_interpreter_cache('stop', [])
endfunction

" Restart the target program by stopping and starting it
function! incpy#Restart()
    for method in ['stop', 'start']
        call s:execute_interpreter_cache(method, [])
    endfor
endfunction

function! incpy#Show()
    let parameters = map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)')
    call s:execute_interpreter_cache_guarded(['show'], parameters, s:get_window_options())
endfunction

function! incpy#Hide()
    call s:execute_interpreter_cache_guarded(['hide'], [])
endfunction

""" Plugin interaction interface
function! incpy#Execute(line)
    call s:execute_interpreter_cache_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())

    call s:execute_interpreter_cache('communicate', [s:quote_single(a:line)])
    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#ExecuteRange() range
    call incpy#Range(a:firstline, a:lastline)
endfunction

function! incpy#ExecuteBlock() range
    let l:block = s:selected_block()
    throw printf('Block range execution is currently not implemented')
endfunction

function! incpy#ExecuteSelected() range
    let l:block = s:selected()
    throw printf('Selection range execution is currently not implemented')
endfunction

function! incpy#Evaluate(expr)
    let stripped = s:strip_by_option(g:incpy#EvalStrip, a:expr)

    " Evaluate and emit an expression in the target using the plugin
    call s:execute_interpreter_cache_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
    call s:communicate_interpreter_encoded(s:singleline(g:incpy#EvalFormat, "\"\\"), stripped)

    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#EvaluateRange() range
    return incpy#Evaluate(join(s:selected_range()))
endfunction

function! incpy#EvaluateBlock() range
    return incpy#Evaluate(join(s:selected_block()))
endfunction

function! incpy#EvaluateSelected() range
    return incpy#Evaluate(join(s:selected()))
endfunction

function! incpy#Halp(expr)
    let LetMeSeeYouStripped = substitute(a:expr, '^[ \t\n]\+\|[ \t\n]\+$', '', 'g')

    " Execute g:incpy#HelpFormat in the target using the plugin's cached communicator
    if len(LetMeSeeYouStripped) > 0
        call s:execute_interpreter_cache_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
        call s:communicate_interpreter_encoded(s:singleline(g:incpy#HelpFormat, "\"\\"), s:escape_double(LetMeSeeYouStripped))
    endif
endfunction

function! incpy#HalpSelected() range
    return incpy#Halp(join(s:selected()))
endfunction

function! incpy#ExecuteFile(filename)
    let open_and_execute = printf("with open(%s) as infile: exec(infile.read())", s:quote_double(a:filename))
    call s:execute_interpreter_cache('communicate', [s:quote_single(open_and_execute), 'silent=True'])
endfunction

""" Internal interface for setting up the plugin loader and packages
function! incpy#SetupPackageLoader(package, path)
    let [l:package_name, l:package_path] = [a:package, fnamemodify(a:path, ":p")]

    let l:loader_closure_name = 'generate_package_loaders'
    let l:loader_closure_definition = s:generate_package_loader_function(l:loader_closure_name)
    execute printf("pythonx %s", l:loader_closure_definition)

    " Next we need to use it with our parameters so that we can
    " create a hidden module to capture any python-specific work.
    let quoted_parameters = map([l:package_name, l:package_path, g:incpy#PluginName], 's:quote_double(v:val)')
    execute printf("pythonx __import__(%s).meta_path.extend(%s(%s))", s:quote_single('sys'), l:loader_closure_name, join(quoted_parameters, ', '))

    " Now that it's been used, we're free to delete it.
    execute printf("pythonx del(%s)", l:loader_closure_name)
endfunction

"" Setting up the interpreter and its view
function! incpy#SetupInterpreter(package)
    let install_interpreter = s:generate_interpreter_cache_snippet(a:package)
    call s:execute_python_in_workspace(a:package, install_interpreter)
endfunction

function! incpy#SetupInterpreterView(package)
    let create_view_code = s:generate_interpreter_view_snippet(a:package)
    call s:execute_python_in_workspace(a:package, create_view_code)
endfunction
