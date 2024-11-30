" Just a utility for generating a python expression that accesses a vim global variable
function! s:generate_gvar_expression(name)
    let interface = [printf('__import__(%s)', incpy#string#quote_single(join([g:incpy#PackageName, 'interface'], '.'))), 'interface']
    let gvars = ['vim', 'gvars']
    return printf("%s[%s]", join(interface + gvars, '.'), incpy#string#quote_double(a:name))
endfunction

" convert from a vim native type to a string that can be interpreted by python
function! s:render_vim_atomic(object)
    let object_type = type(a:object)
    if object_type == v:t_number
        return printf('%d', a:object)
    elseif object_type == v:t_string
        return incpy#string#quote_single(a:object)
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
function! incpy#python#render(object)
    let object_type = type(a:object)
    if object_type == v:t_list
        let items = map(a:object, 'incpy#python#render(v:val)')
        return printf('[%s]', join(items, ','))
    elseif object_type == v:t_dict
        let rendered = map(a:object, 'printf("%s:%s", incpy#python#render(v:key), incpy#python#render(v:val))')
        let items = map(keys(rendered), 'get(rendered, v:val)')
        return printf('{%s}', join(items, ','))
    else
        return s:render_vim_atomic(a:object)
    endif
endfunction

""" Utilities related to executing python
function! s:execute_python_in_workspace(package, command)
    let l:multiline_command = split(a:command, "\n")
    let l:workspace_module = join([a:package, 'workspace'], '.')

    " Guard whatever it is we were asked to execute by
    " ensuring that our module workspace has been loaded.
    execute printf("pythonx (__builtins__ if isinstance(__builtins__, {}.__class__) else __builtins__.__dict__)['__import__'](%s).exec_", incpy#string#quote_single(a:package))
    execute printf("pythonx (__builtins__ if isinstance(__builtins__, {}.__class__) else __builtins__.__dict__)['__import__'](%s)", incpy#string#quote_single(l:workspace_module))

    " If our command contains 3x single or double-quotes, then
    " we format our strings with the one that isn't used.
    if stridx(a:command, '"""') < 0
        let strings = printf("%s\n%s\n%s", 'r"""', join(l:multiline_command, "\n"), '"""')
    else
        let strings = printf("%s\n%s\n%s", "r'''", join(l:multiline_command, "\n"), "'''")
    endif

    " Now we need to render our multilined list of commands to
    " a multilined string, and then execute it in our workspace.
    let l:because_neovim = printf('(__builtins__ if isinstance(__builtins__, {}.__class__) else __builtins__.__dict__)[%s]', incpy#string#quote_single('__import__'))
    let l:python_execute = join([printf("%s(%s)", l:because_neovim, incpy#string#quote_single(a:package)), 'exec_'], '.')
    let l:python_workspace = join([printf("%s(%s)", l:because_neovim, incpy#string#quote_single(l:workspace_module)), 'workspace', '__dict__'], '.')

    execute printf("pythonx (lambda F, ns: (lambda s: F(s, ns, ns)))(%s, %s)(%s)", l:python_execute, l:python_workspace, strings)
endfunction

function! incpy#python#execute(method, parameters, keywords={})
    let l:cache = [printf('__import__(%s)', incpy#string#quote_single(g:incpy#PackageName)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    let l:kwparameters = len(a:keywords)? [printf('**%s', incpy#python#render(a:keywords))] : []
    call s:execute_python_in_workspace(g:incpy#PackageName, printf('%s(%s)', join(l:cache + l:method, '.'), join(a:parameters + l:kwparameters, ', ')))
endfunction

function! incpy#python#execute_guarded(method, parameters, keywords={})
    let l:cache = [printf('__import__(%s)', incpy#string#quote_single(g:incpy#PackageName)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    let l:kwparameters = len(a:keywords)? [printf('**%s', incpy#python#render(a:keywords))] : []
    call s:execute_python_in_workspace(g:incpy#PackageName, printf("hasattr(%s, %s) and %s(%s)", join(slice(l:cache, 0, -1), '.'), incpy#string#quote_single(l:cache[-1]), join(l:cache + l:method, '.'), join(a:parameters + l:kwparameters, ', ')))
endfunction

function! incpy#python#communicate(format, code)
    let l:cache = [printf('__import__(%s)', incpy#string#quote_single(g:incpy#PackageName)), 'cache']
    let l:encoded = substitute(a:code, '.', '\=printf("\\x%02x", char2nr(submatch(0)))', 'g')
    let l:lambda = printf("(lambda interpreter: (lambda code: interpreter.communicate(code)))(%s)", join(cache, '.'))
    execute printf("pythonx %s(\"%s\".format(\"%s\"))", l:lambda, a:format, l:encoded)
endfunction

function! s:get_window_options(other={})
    let core = g:incpy#CoreWindowOptions

    " Initialize our result dictionary with the core window options.
    let result = {}
    for o in keys(core)
        let result[o] = core[o]
    endfor

    " Specially handle the window preview option. This dictionary key isn't an
    " option, but is used to influence the command used to create the window.
    if exists('g:incpy#WindowPreview')
        let result['preview'] = g:incpy#WindowPreview
    endif

    " Merge in any custom window options that were assigned.
    for o in keys(g:incpy#WindowOptions)
        let result[o] = g:incpy#WindowOptions[o]
    endfor

    " Merge in any of the other options that we were given.
    for o in keys(a:other)
        let result[o] = a:other[o]
    endfor
    return result
endfunction

""" Public interface and management

" Execute the specified lines within the current interpreter.
function! incpy#python#Range(begin, end)
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

    " Show the window and then send each line to the interpreter.
    call incpy#python#execute_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
    let l:commands_stripped = (type(code_stripped) == v:t_list)? code_stripped : [code_stripped]
    for command_stripped in l:commands_stripped
        call incpy#python#communicate(incpy#string#singleline(g:incpy#ExecFormat, "\"\\"), command_stripped)
    endfor

    " If the user configured us to follow the output, then do as we were told.
    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

" Start the target program and attach it to a buffer
function! incpy#python#Start()
    call incpy#python#execute('start', [])
endfunction

" Stop the target program and detach it from its buffer
function! incpy#python#Stop()
    call incpy#python#execute('stop', [])
endfunction

" Restart the target program by stopping and starting it
function! incpy#python#Restart()
    for method in ['stop', 'start']
        call incpy#python#execute(method, [])
    endfor
endfunction

function! incpy#python#Show()
    let parameters = map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)')
    call incpy#python#execute_guarded(['show'], parameters, s:get_window_options())
endfunction

function! incpy#python#Hide()
    call incpy#python#execute_guarded(['hide'], [])
endfunction

""" Plugin interaction interface
function! incpy#python#Execute(line)
    let input_stripped = incpy#string#strip(g:incpy#InputStrip, a:line)
    if index([v:t_string, v:t_list], type(input_stripped)) < 0
        throw printf("Unable to process the given input due to it being of an unsupported type (%s): %s", typename(input_stripped), input_stripped)
    endif

    " Now we need to strip our input for execution.
    let code_stripped = incpy#string#strip(g:incpy#ExecStrip, input_stripped)
    if !(type(code_stripped) == v:t_string || type(code_stripped) == v:t_list)
        throw printf("Unable to execute due to an unknown input type (%s) being returned by %s: %s", typename(code_stripped), 'g:incpy#ExecStrip', code_stripped)
    endif

    " Show the window and send each line from our input to the interpreter.
    call incpy#python#execute_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
    let l:commands_stripped = (type(code_stripped) == v:t_list)? code_stripped : [code_stripped]
    for command_stripped in l:commands_stripped
        call incpy#python#communicate(incpy#string#singleline(g:incpy#ExecFormat, "\"\\"), command_stripped)
    endfor

    " If the user configured us to follow the output, then do as we were told.
    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#python#ExecuteRaw(line)
    call incpy#python#execute_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
    call incpy#python#communicate("{}", a:line)
    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#python#Evaluate(expr)
    let stripped = incpy#string#strip(g:incpy#EvalStrip, a:expr)

    " Evaluate and emit an expression in the target using the plugin
    call incpy#python#execute_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
    call incpy#python#communicate(incpy#string#singleline(g:incpy#EvalFormat, "\"\\"), stripped)

    if g:incpy#OutputFollow
        try | call incpy#ui#window#tail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#python#Halp(expr)
    let LetMeSeeYouStripped = substitute(a:expr, '^[ \t\n]\+\|[ \t\n]\+$', '', 'g')

    " Execute g:incpy#HelpFormat in the target using the plugin's cached communicator
    if len(LetMeSeeYouStripped) > 0
        call incpy#python#execute_guarded(['show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'), s:get_window_options())
        call incpy#python#communicate(incpy#string#singleline(g:incpy#HelpFormat, "\"\\"), incpy#string#escape_double(LetMeSeeYouStripped))
    endif
endfunction

function! incpy#python#ExecuteFile(filename)
    let open_and_execute = printf("with open(%s) as infile: exec(infile.read())", incpy#string#quote_double(a:filename))
    call incpy#python#execute('communicate', [incpy#string#quote_single(open_and_execute), 'silent=True'])
endfunction

""" Dynamically generated python code used during setup

"" Interface for setting up the plugin loader and its module/package by name.
function! incpy#python#load_package(package, path)
    let [l:package_name, l:package_path] = [a:package, fnamemodify(a:path, ":p")]

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

    let l:loader_closure_name = 'generate_package_loaders'
    let l:loader_closure_definition = printf(join(unnamed_definition, "\n"), l:loader_closure_name)
    execute printf("pythonx %s", l:loader_closure_definition)

    " Next we need to use it with our parameters so that we can
    " create a hidden module to capture any python-specific work.
    let quoted_parameters = map([l:package_name, l:package_path, g:incpy#PluginName], 'incpy#string#quote_double(v:val)')
    execute printf("pythonx __import__(%s).meta_path.extend(%s(%s))", incpy#string#quote_single('sys'), l:loader_closure_name, join(quoted_parameters, ', '))

    " Now that it's been used, we're free to delete it.
    execute printf("pythonx del(%s)", l:loader_closure_name)
endfunction

"" Setting up the interpreter after it has been chosen.
function! incpy#python#setup(package)

    let install_interpreter =<< trim EOC
        __import__, package_name = (__builtins__ if isinstance(__builtins__, {}.__class__) else __builtins__.__dict__)['__import__'], %s
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

    let code = printf(join(install_interpreter, "\n"), incpy#string#quote_single(a:package))
    call s:execute_python_in_workspace(a:package, code)
endfunction

"" Setting up the interpreter's view after it was initialized.
function! incpy#python#setup_view(package)

    let create_view =<< trim EOC
        package_name = %s

        __import__ = (__builtins__ if isinstance(__builtins__, {}.__class__) else __builtins__.__dict__)['__import__']
        package = __import__(package_name)
        [interface] = (getattr(__import__('.'.join([package.__name__, module])), module) for module in ['interface'])

        # grab the cached interpreter out of the package
        cache = package.cache

        # now we just need to store its buffer id
        interface.vim.gvars['incpy#BufferId'] = cache.view.buffer.number
    EOC

    let code = printf(join(create_view, "\n"), incpy#string#quote_single(a:package))
    return s:execute_python_in_workspace(a:package, code)
endfunction
