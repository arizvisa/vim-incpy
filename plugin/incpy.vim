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
    let defopts["Terminal"] = has('terminal') || has('nvim')

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
    let neo_window_options = {'buftype': 'nofile', 'swapfile': v:false, 'updatecount':0, 'buflisted': v:false}
    let core_window_options = {'buftype': has('terminal')? 'terminal' : 'nowrite', 'swapfile': v:false, 'updatecount':0, 'buflisted': v:false}
    let defopts["CoreWindowOptions"] = has('nvim')? neo_window_options : core_window_options

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
    elseif len(g:incpy#Program) > 0 && !(has('terminal') || has('nvim'))
        echohl WarningMsg | echomsg printf('WARNING:%s:Using plugin to run an external program without support for greenlets could be unstable', g:incpy#PluginName) | echohl None
    endif

    " Now we can setup the interpreter and its view.
    call incpy#SetupInterpreter(a:package)
    call incpy#SetupInterpreterView(a:package)

endfunction

""" Mapping of vim commands and keys

" Create some vim commands that can interact with the plugin
function! incpy#SetupCommands()
    command PyLine call incpy#Range(line("."), line("."))
    command PyBuffer call incpy#Range(0, line('$'))
    command -range PyRange call incpy#Range(<line1>, <line2>)

    command -nargs=1 Py call incpy#Execute(<q-args>)
    command -range PyExecuteRange <line1>,<line2>call incpy#ExecuteRange()
    command -range PyExecuteBlock <line1>,<line2>call incpy#ExecuteBlock()
    command -range PyExecuteSelection <line1>,<line2>call incpy#ExecuteSelected()

    command -nargs=1 PyEval call incpy#Evaluate(<q-args>)
    command -range PyEvalRange <line1>,<line2>call incpy#EvaluateRange()
    command -range PyEvalBlock <line1>,<line2>call incpy#EvaluateBlock()
    command -range PyEvalSelection <line1>,<line2>call incpy#EvaluateSelected()

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
