""" Utilities related to executing code within vim's internal instance of python.

" This function will execute the code in a:command within the namespace
" underneath the specified a:package name as "package.workspace".
function! incpy#internal#workspace(package, command)
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

" Execute the a:method for the "cache" object from the a:package module.
function! incpy#internal#execute(package, method, parameters, keywords={})
    let l:cache = [printf('__import__(%s)', incpy#string#quote_single(a:package)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    let l:kwparameters = len(a:keywords)? [printf('**%s', incpy#python#render(a:keywords))] : []
    call incpy#internal#workspace(a:package, printf('%s(%s)', join(l:cache + l:method, '.'), join(a:parameters + l:kwparameters, ', ')))
endfunction

" Execute the a:method for the "cache" object in the module a:package iff the
" attribute for the specified method name actually exists.
function! incpy#internal#execute_guarded(package, method, parameters, keywords={})
    let l:cache = [printf('__import__(%s)', incpy#string#quote_single(a:package)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    let l:kwparameters = len(a:keywords)? [printf('**%s', incpy#python#render(a:keywords))] : []
    call incpy#internal#workspace(a:package, printf("hasattr(%s, %s) and %s(%s)", join(slice(l:cache, 0, -1), '.'), incpy#string#quote_single(l:cache[-1]), join(l:cache + l:method, '.'), join(a:parameters + l:kwparameters, ', ')))
endfunction

" Send the specified a:code to the interpreter that is stored within the
" module specified by a:package.
function! incpy#internal#communicate(package, format, code)
    let l:cache = [printf('__import__(%s)', incpy#string#quote_single(a:package)), 'cache']
    let l:encoded = substitute(a:code, '.', '\=printf("\\x%02x", char2nr(submatch(0)))', 'g')
    let l:lambda = printf("(lambda interpreter: (lambda code: interpreter.communicate(code)))(%s)", join(cache, '.'))
    execute printf("pythonx %s(\"%s\".format(\"%s\"))", l:lambda, a:format, l:encoded)
endfunction

""" Utilities for setting up the plugin with dynamically generated python code.

" Interface for creating a temporal module with the name specified by a:package
" using the python modules that can be found at the specified a:path. This is
" done by creating a meta-path finder object and adding it to `sys.meta_path`.
function! incpy#internal#load(package, path)
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

" Responsible for actually choosing and setting up the interpreter. The
" interpreter gets stored within the module specified by a:package.
function! incpy#internal#setup(package)

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
    return incpy#internal#workspace(a:package, code)
endfunction

" Responsible for setting up the view for the interpreter that was initialized.
" The module used to find the interpreter can be specified with a:package.
function! incpy#internal#setup_view(package)

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
    return incpy#internal#workspace(a:package, code)
endfunction
