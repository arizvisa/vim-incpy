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
" bool   g:incpy#WindowFixed    -- refuse to allow automatic resizing of the window.
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

""" Utility functions for indentation, stripping, string processing, etc.

" count the whitespace that prefixes a single-line string
function! s:count_indent(string)
    let characters = 0
    for c in split(a:string, '\zs')
        if stridx(" \t", c) == -1
            break
        endif
        let characters += 1
    endfor
    return characters
endfunction

" find the smallest common indent of a list of strings
function! s:find_common_indent(lines)
    let smallestindent = -1
    for l in a:lines

        " skip lines that are all whitespace
        if strlen(l) == 0 || l =~ '^\s\+$'
            continue
        endif

        let spaces = s:count_indent(l)
        if smallestindent < 0 || spaces < smallestindent
            let smallestindent = spaces
        endif
    endfor
    return smallestindent
endfunction

" strip the specified number of characters from a list of lines
function! s:strip_common_indent(lines, size)
    let results = []
    let prevlength = 0

    " iterate through each line
    for l in a:lines

        " if the line is empty, then pad it with the previous indent
        if strlen(l) == 0
            let row = repeat(" ", prevlength)

        " otherwise remove the requested size, and count the leftover indent
        else
            let row = strpart(l, a:size)
            let prevlength = s:count_indent(row)
        endif

        " append our row to the list of results
        let results += [row]
    endfor
    return results
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

function! s:python_strip_and_fix_indent(lines)
    let indentsize = s:find_common_indent(a:lines)
    let stripped = s:strip_common_indent(a:lines, indentsize)

    " trim any beginning lines that are meaningless
    let l:start = 0
    for l:index in range(len(stripped))
        let l:item = stripped[l:index]
        if strlen(l:item) > 0 && l:item !~ '^\s\+$'
            break
        endif
        let l:start += 1
    endfor

    " trim any ending lines that are meaningless
    let l:tail = 0
    for l:index in range(len(stripped))
        let l:tail += 1
        let l:item = stripped[-(1 + l:index)]
        if strlen(l:item) > 0 && l:item !~ '^\s\+$'
            break
        endif
    endfor

    " if the last line is indented, then we append another newline (python)
    let trimmed = split(trim(join(stripped[l:start : -l:tail], "\n"), " \t\n", 2), "\n")
    if len(trimmed) > 0 && trimmed[-1] =~ '^\s\+'
        let result = add(trimmed, '')
    else
        let result = trimmed
    endif
    return join(result, "\n") .. "\n"
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

""" Miscellaneous utilities related to python
function! s:keyword_under_cursor()
    let res = expand("<cexpr>")
    return len(res)? res : expand("<cword>")
endfunction

function! s:pyexpr_under_cursor()
    let [cword, l:line, cpos] = [expand("<cexpr>"), getline(line('.')), col('.') - 1]

    " Patterns which are used to find pieces of the expression. We depend on the
    " iskeyword character set always placing us at the beginning of an identifier.
    let pattern_conversion = ['-', '+', '~']
    let pattern_group = ['()', '[]', '{}']

    "" The logic for trying to determine the quotes for a string is pretty screwy.
    let pattern_string = ['''', '"']

    " Start out by splitting up our pattern group into a list that can be used.
    let _pattern_begin_list = reduce(pattern_group, { items, pair -> items + [pair[0]] }, [])
    let _pattern_end_list = reduce(pattern_group, { items, pair -> items + [pair[1]] }, [])

    " Figure out where the beginning of the current expression is at.
    let rpos = strridx(l:line, cword, cpos)
    if rpos >= 0 && cpos - rpos < len(cword)
        let start = strridx(l:line, cword, cpos)
    else
        let start = stridx(l:line, cword, cpos)
    endif

    " If we're at the beginning of a string or a group, then trust what the user gave us.
    if index(_pattern_begin_list + pattern_string, l:line[cpos]) >= 0
        let start = cpos

    " Otherwise, use the current expression. But if there's a sign in front, then use it.
    else
        let start = (index(pattern_conversion, l:line[start - 1]) < 0)? start : start - 1
    endif

    " Find the ending (space, quote, terminal-grouping) from `start` and trim spaces for the result.
    let stop = match(l:line, printf('[[:space:]%s]', join(pattern_string + map(copy(pattern_group), 'printf("\\%s", v:val[1])'), '')), start)
    let result = trim(l:line[start : stop])

    " If the result is an empty string, then strip quotes and bail with what we fetched.
    let _pattern_string = join(pattern_string, '')
    if match(result, printf('^[%s]\+$', pattern_string)) >= 0
        return trim(result, _pattern_string)
    endif

    " Otherwise we need to scan for the beginning and ending to determine the quoting type.
    let prefix = (start > 0)? matchstr(l:line[: start - 1], printf('[%s]\+$', _pattern_string)) : ''
    let trailer = matchstr(result, printf('[%s]\+$', _pattern_string))

    " If we have a prefix then trust it first. For python if the length >= 3, and it's duplicated,
    " then we trim it. Otherwise we can just take the first quote type that we found and use that.
    if len(prefix)
        if len(prefix < 3) || match(prefix, printf("^[%s]\{3\}", prefix[0])) < 0
            let [lside, rside] = [prefix[0], prefix[0]]
        else
            let [lside, rside] = [prefix[:3], prefix[:3]]
        endif

        return join([lside, trim(result, _pattern_string), rside], '')

    " If we got a trailer without the prefix, then scan for its terminator and update the result.
    elseif len(trailer)
        let qindex = stridx(l:line, trailer, stop + 1)
        let result = (qindex < 0)? result : join([result, strpart(l:line, stop + 1, qindex)], '')
    endif

    " Otherwise we count everything... ignoring how they are nested because we're writing fucking vimscript.
    let counts = {}
    for pair in pattern_group
        let counts[pair[0]] = count(result, pair[0])
        let counts[pair[1]] = count(result, pair[1])
    endfor

    " If there aren't any begin-group characters, then we can just trim and return it.
    if reduce(_pattern_begin_list, { total, character -> total + counts[character] }, 0) == 0
        return trim(result, join(_pattern_end_list, ''))
    endif

    " Otherwise, we've hit the worst-case and we need to iterate through the result to
    " collect the order we close the expression with and map them to the right character.
    let [order, _pattern_group_table] = [[], {}]
    for pair in pattern_group | let _pattern_group_table[pair[0]] = pair[1] | endfor

    " Push them onto a stack instead of appending to a list in order to save a reverse.
    for character in result
        if index(_pattern_begin_list, character) >= 0
            let order = [_pattern_group_table[character]] + order
        endif
    endfor

    " Now we can trim and append the determined order to our result.
    let trimmed = trim(result, join(_pattern_end_list, ''), 2)
    return join([trimmed, join(order, '')], '')
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

function! s:execute_interpreter_cache(method, parameters)
    let l:cache = [printf('__import__(%s)', s:quote_single(g:incpy#PackageName)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    call s:execute_python_in_workspace(g:incpy#PackageName, printf('%s(%s)', join(l:cache + l:method, '.'), join(a:parameters, ', ')))
endfunction

function! s:execute_interpreter_cache_guarded(method, parameters)
    let l:cache = [printf('__import__(%s)', s:quote_single(g:incpy#PackageName)), 'cache']
    let l:method = (type(a:method) == v:t_list)? a:method : [a:method]
    call s:execute_python_in_workspace(g:incpy#PackageName, printf("hasattr(%s, %s) and %s(%s)", join(slice(l:cache, 0, -1), '.'), s:quote_single(l:cache[-1]), join(l:cache + l:method, '.'), join(a:parameters, ', ')))
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
        use_terminal = interface.vim.eval('has("terminal")') and interface.vim.gvars["incpy#Terminal"]

        # spawn interpreter requested by user with the specified options
        opt = {'winfixwidth':True, 'winfixheight':True} if interface.vim.gvars["incpy#WindowFixed"] > 0 else {}
        try:
            if len(program) > 0:
                interpreter = interpreters.terminal if use_terminal else interpreters.external
                cache = interpreter.new(program, opt=opt)
            else:
                interpreter = interpreters.python_internal
                cache = interpreter.new(opt=opt)

        # if we couldn't start the interpreter, then fall back to an internal one
        except Exception:
            logger.fatal("error starting external interpreter: {:s}".format(program), exc_info=True)
            logger.warning("falling back to internal python interpreter")
            cache = interpreters.python_internal.new(opt=opt)

        # assign the interpreter object into our package
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

""" Public interface and management

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
    call s:execute_interpreter_cache_guarded(['view', 'show'], parameters)
endfunction

function! incpy#Hide()
    call s:execute_interpreter_cache_guarded(['view', 'hide'], [])
endfunction

" Attach or detach a buffer from the interpreter to a window
function! incpy#Attach()
    call s:execute_interpreter_cache_guarded('attach', [])
endfunction

function! incpy#Detach()
    call s:execute_interpreter_cache_guarded('detach', [])
endfunction

""" Plugin interaction interface
function! incpy#Execute(line)
    call s:execute_interpreter_cache_guarded(['view', 'show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'))

    call s:execute_interpreter_cache('communicate', [s:quote_single(a:line)])
    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

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
    call s:execute_interpreter_cache_guarded(['view', 'show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'))

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

function! incpy#Evaluate(expr)
    let stripped = s:strip_by_option(g:incpy#EvalStrip, a:expr)

    " Evaluate and emit an expression in the target using the plugin
    call s:execute_interpreter_cache_guarded(['view', 'show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'))
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

function! incpy#Halp(expr)
    let LetMeSeeYouStripped = substitute(a:expr, '^[ \t\n]\+\|[ \t\n]\+$', '', 'g')

    " Execute g:incpy#HelpFormat in the target using the plugin's cached communicator
    if len(LetMeSeeYouStripped) > 0
        call s:execute_interpreter_cache_guarded(['view', 'show'], map(['incpy#WindowPosition', 'incpy#WindowRatio'], 's:generate_gvar_expression(v:val)'))
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

""" Plugin options and setup
function! incpy#SetupOptions()
    let defopts = {}

    let defopts["PackageName"] = '__incpy__'
    let defopts["PluginName"] = 'incpy'

    " Set any default options for the plugin that the user missed
    let defopts["Program"] = ""
    let defopts["Echo"] = v:true
    let defopts["OutputFollow"] = v:true
    let defopts["WindowName"] = "Scratch"
    let defopts["WindowRatio"] = 1.0/3
    let defopts["WindowPosition"] = "below"
    let defopts["WindowOptions"] = {}
    let defopts["WindowPreview"] = v:false
    let defopts["WindowFixed"] = 0
    let defopts["WindowStartup"] = v:true

    let defopts["Greenlets"] = v:false
    let defopts["Terminal"] = has('terminal')

    let python_builtins = printf("__import__(%s)", s:quote_double('builtins'))
    let python_pydoc = printf("__import__(%s)", s:quote_double('pydoc'))
    let python_sys = printf("__import__(%s)", s:quote_double('sys'))
    let python_help = join([python_builtins, 'help'], '.')
    let defopts["HelpFormat"] = printf("%s.getpager = lambda: %s.plainpager\ntry:exec(\"%s({0})\")\nexcept SyntaxError:%s(\"{0}\")\n\n", python_pydoc, python_pydoc, escape(python_help, "\"\\"), python_help)

    let defopts["InputStrip"] = function("s:python_strip_and_fix_indent")
    let defopts["EchoFormat"] = "# >>> {}"
    let defopts["EchoNewline"] = "{}\n"
    let defopts["EvalFormat"] = printf("%s.displayhook(({}))\n", python_sys)
    let defopts["EvalStrip"] = v:false
    let defopts["ExecFormat"] = "{}\n"
    let defopts["ExecStrip"] = v:false

    " If the PYTHONSTARTUP environment-variable exists, then use it. Otherwise use the default one.
    if exists("$PYTHONSTARTUP")
        let defopts["PythonStartup"] = $PYTHONSTARTUP
    else
        let defopts["PythonStartup"] = printf("%s/.pythonrc.py", $HOME)
    endif

    " Default window options that the user will override
    let defopts["CoreWindowOptions"] = {"buftype": has("terminal")? "terminal" : "nowrite", "swapfile": v:false, "updatecount":0, "buflisted": v:false}

    " If any of these options aren't defined during evaluation, then go through and assign them as defaults
    for o in keys(defopts)
        if ! exists("g:incpy#{o}")
            let g:incpy#{o} = defopts[o]
        endif
    endfor
endfunction

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
    elseif len(g:incpy#Program) > 0 && !has("terminal")
        echohl WarningMsg | echomsg printf('WARNING:%s:Using plugin to run an external program without support for greenlets could be unstable', g:incpy#PluginName) | echohl None
    endif

    " Now we can setup the interpreter and its view.
    call incpy#SetupInterpreter(a:package)
    call incpy#SetupInterpreterView(a:package)

    """ Set any of the specified options for the interpreter interface.
    if g:incpy#WindowStartup | call incpy#Show() | endif

endfunction

""" Mapping of vim commands and keys

" Create some vim commands that can interact with the plugin
function! incpy#SetupCommands()
    command PyLine call incpy#Range(line("."), line("."))
    command PyBuffer call incpy#Range(0, line('$'))

    command -nargs=1 Py call incpy#Execute(<q-args>)
    command -range PyRange call incpy#Range(<line1>, <line2>)

    command -nargs=1 PyEval call incpy#Evaluate(<q-args>)
    command -range PyEvalRange <line1>,<line2>call incpy#EvaluateRange()
    command -range PyEvalBlock <line1>,<line2>call incpy#EvaluateBlock()
    command -range PyEvalSelection call incpy#Evaluate(s:selected())
    command -nargs=1 PyHelp call incpy#Halp(<q-args>)
    command -range PyHelpSelection <line1>,<line2>call incpy#HalpSelected()
endfunction

" Set up the default key mappings for vim to use the plugin
function! incpy#SetupKeys()

    " Execute a single or range of lines
    nnoremap ! :PyLine<C-M>
    vnoremap ! :PyRange<C-M>

    " Python visual and normal mode mappings
    nnoremap <C-/> :call incpy#Evaluate(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-/> :PyEvalRange<C-M>

    nnoremap <C-\> :call incpy#Evaluate(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-\> :PyEvalRange<C-M>

    " Normal and visual mode mappings for windows
    nnoremap <C-@> :call incpy#Halp(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-@> :PyHelpSelection<C-M>

    " Normal and visual mode mappings for everything else
    nnoremap <C-S-@> :call incpy#Halp(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-S-@> :PyHelpSelection<C-M>
endfunction

" Check to see if a python site-user dotfile exists in the users home-directory.
function! incpy#ImportDotfile()
    let l:dotfile = g:incpy#PythonStartup
    if filereadable(l:dotfile)
        call incpy#ExecuteFile(l:dotfile)
    endif
endfunction

"" Entry point
function! incpy#LoadPlugin()
    let s:current_script=expand("<sfile>:p:h")

    call incpy#SetupOptions()
    call incpy#SetupPythonLoader(g:incpy#PackageName, s:current_script)
    call incpy#SetupPythonInterpreter(g:incpy#PackageName)
    call incpy#SetupCommands()
    call incpy#SetupKeys()

    " if we're using an external program, then we can just ignore the dotfile
    " since it really only makes sense when using the python interpreter.
    if g:incpy#Program == ""
        call incpy#ImportDotfile()
    endif

    " on entry, silently import the user module to honor any user-specific configurations
    autocmd VimEnter * call incpy#Attach()
    autocmd VimLeavePre * call incpy#Detach()

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
