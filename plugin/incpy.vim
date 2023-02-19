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
" bool   g:incpy#Greenlets    -- whether to use greenlets (lightweight-threads) or not.
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
" string g:incpy#WindowPosition -- the position at which to create the window. can be
"                                  either "above", "below", "left", or "right".
" string g:incpy#PythonStartup  -- the name of the dotfile to seed python's globals with.
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

if has("python") || has("python3")

""" Utility functions for indentation stuff
function! s:count_indent(string)
    " count the whitespace that prefixes a single-line string
    let characters = 0
    for c in split(a:string, '\zs')
        if stridx(" \t", c) == -1
            break
        endif
        let characters += 1
    endfor
    return characters
endfunction

function! s:find_common_indent(lines)
    " find the smallest common indent of a list of strings
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

function! s:strip_common_indent(lines, size)
    " strip the specified number of characters from a list of lines

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
    let trimmed = stripped[l:start : -l:tail]
    if len(trimmed) > 0
        let result = trimmed[-1] =~ '^\s\+'? trimmed + [''] : trimmed
    else
        let result = trimmed
    endif
    return result
endfunction

function! s:striplist_by_option(option, lines)
    let items = a:lines

    " Strip the fetched lines if the user configured us to
    if type(a:option) == v:t_bool
        let result = a:option == v:true? map(items, "trim(v:val)") : items

    " If the type is a string, then use it as a regex that
    elseif type(a:option) == v:t_string
        let result = map(items, a:option)

    "  Otherwise it's a function to use as a transformation
    elseif type(a:option) == v:t_func
        let F = a:option
        let result = F(items)

    else
        throw printf("Unknown filtering option (%s): %s", typename(a:option), a:option)
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
        throw printf("Unknown filtering option (%s): %s", typename(a:option), a:option)
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

""" Window management
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

""" Miscellanous utilities
function! s:selected() range
    " really, vim? really??
    let oldvalue = getreg("")
    normal gvy
    let result = getreg("")
    call setreg("", oldvalue)
    return result
endfunction

function! s:singleline(string, escape)
    " escape the multiline string with the specified characters and return it as a single-line string
    let escaped = escape(a:string, a:escape)
    let result = substitute(escaped, "\n", "\\\\n", "g")
    return result
endfunction

""" Interface for setting up the plugin
function! incpy#SetupOptions()
    " Set any default options for the plugin that the user missed
    let defopts = {}
    let defopts["Program"] = ""
    let defopts["Greenlets"] = v:false
    let defopts["Echo"] = v:true
    let defopts["OutputFollow"] = v:true
    let defopts["WindowName"] = "Scratch"
    let defopts["WindowRatio"] = 1.0/3
    let defopts["WindowPosition"] = "below"
    let defopts["WindowOptions"] = {}
    let defopts["WindowPreview"] = v:false
    let defopts["WindowFixed"] = 0
    let python_builtins = "__import__(\"builtins\")"
    let python_pydoc = "__import__(\"pydoc\")"
    let defopts["HelpFormat"] = printf("%s.getpager = lambda: %s.plainpager\ntry:exec(\"%s.help({0})\")\nexcept SyntaxError:%s.help(\"{0}\")\n\n", python_pydoc, python_pydoc, escape(python_builtins, "\"\\"), python_builtins)
    let python_sys = "__import__(\"sys\")"

    let defopts["InputStrip"] = function("s:python_strip_and_fix_indent")
    let defopts["EchoFormat"] = "# >>> {}"
    let defopts["EchoNewline"] = "{}\n"
    " let defopts["EvalFormat"] = printf("_={};print _')", python_builtins, python_builtins, python_builtins)
    " let defopts["EvalFormat"] = printf("__incpy__.sys.displayhook({})')")
    " let defopts["EvalFormat"] = printf("__incpy__.builtins._={};print __incpy__.__builtin__._")
    let defopts["EvalFormat"] = printf("%s.displayhook({})\n", python_sys)
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

function! incpy#SetupPython(currentscriptpath)
    " Set up the module search path to include the script's "python" directory
    let m = substitute(a:currentscriptpath, "\\", "/", "g")

    " FIXME: use sys.meta_path

    " setup the default logger
    pythonx __import__('logging').basicConfig()
    pythonx __import__('logging').getLogger('incpy')

    " add the python path using the runtimepath directory that this script is contained in
    for p in split(&runtimepath, ",")
        let p = substitute(p, "\\", "/", "g")
        if stridx(m, p, 0) == 0
            execute printf("pythonx __import__('sys').path.append('%s/python')", p)
            return
        endif
    endfor

    " otherwise, look up from our current script's directory for a python sub-directory
    let p = finddir("python", m . ";")
    if isdirectory(p)
        execute printf("pythonx __import__('sys').path.append('%s')", p)
        return
    endif

    throw printf("Unable to determine basepath from script %s", m)
endfunction

function! incpy#ImportDotfile()
    " Check to see if a python site-user dotfile exists in the users home-directory.
    let source = g:incpy#PythonStartup
    if filereadable(source)
        let input = printf("with open(\"%s\") as infile: exec(infile.read())", escape(source, "\"\\"))
        execute printf("pythonx __incpy__.cache.communicate('%s', silent=True)", escape(input, "'\\"))
    endif
endfunction

""" Mapping of vim commands and keys
function! incpy#SetupCommands()
    " Create some vim commands that interact with the plugin
    command PyLine call incpy#Range(line("."), line("."))
    command PyBuffer call incpy#Range(0, line('$'))

    command -nargs=1 Py call incpy#Execute(<q-args>)
    command -range PyRange call incpy#Range(<line1>, <line2>)

    command -nargs=1 PyEval call incpy#Evaluate(<q-args>)
    command -range PyEvalRange <line1>,<line2>call incpy#Evaluate(s:selected())
    command -nargs=1 PyHelp call incpy#Halp(<q-args>)
    command -range PyHelpRange <line1>,<line2>call incpy#Halp(s:selected())
endfunction

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

function! incpy#SetupKeys()
    " Set up the default key mappings for vim to use the plugin
    nnoremap ! :PyLine<C-M>
    vnoremap ! :PyRange<C-M>

    " Python visual and normal mode mappings
    nnoremap <C-/> :call incpy#Evaluate(<SID>pyexpr_under_cursor())<C-M>
    vnoremap <C-/> :PyEvalRange<C-M>

    nnoremap <C-\> :call incpy#Evaluate(<SID>pyexpr_under_cursor())<C-M>
    vnoremap <C-\> :PyEvalRange<C-M>

    " Normal and visual mode mappings for windows
    nnoremap <C-@> :call incpy#Halp(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-@> :PyHelpRange<C-M>

    " Normal and visual mode mappings for everything else
    nnoremap <C-S-@> :call incpy#Halp(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-S-@> :PyHelpRange<C-M>
endfunction

"" Define the whole python interface for the plugin
function! incpy#Setup()

    " Set any the options for the python module part.
    if g:incpy#Greenlets
        " If greenlets were specified, then enable it by importing 'gevent' into the current python environment
        pythonx __import__('gevent')
    elseif g:incpy#Program != "" && !has("terminal")
        " Otherwise we only need to warn the user that they should use it if they're trying to run an external program
        echohl WarningMsg | echomsg "WARNING:incpy.vim:Using vim-incpy to run an external program without support for greenlets will be unstable" | echohl None
    endif

    " Initialize the python __incpy__ namespace
    pythonx <<EOF

# create a pseudo-builtin module
__incpy__ = __builtins__.__class__('__incpy__', 'Internal state module for vim-incpy')
__incpy__.sys, __incpy__.incpy, __incpy__.builtins, __incpy__.six = __import__('sys'), __import__('incpy'), __import__('builtins'), __import__('six')
__incpy__.vim, __incpy__.buffer, __incpy__.spawn = __incpy__.incpy.vim, __incpy__.incpy.buffer, __incpy__.incpy.spawn

# save initial state
__incpy__.state = __incpy__.builtins.tuple(__incpy__.builtins.getattr(__incpy__.sys, _) for _ in ['stdin', 'stdout', 'stderr'])
__incpy__.logger = __import__('logging').getLogger('incpy').getChild('vim')

# interpreter classes
class interpreter(object):
    # options that are used for constructing the view
    view_options = ['buffer', 'opt', 'preview', 'tab']

    @__incpy__.builtins.classmethod
    def new(cls, **options):
        options.setdefault('buffer', None)
        return cls(**options)

    def __init__(self, **kwds):
        opt = {}.__class__(__incpy__.vim.gvars['incpy#CoreWindowOptions'])
        opt.update(__incpy__.vim.gvars['incpy#WindowOptions'])
        opt.update(kwds.pop('opt', {}))
        kwds.setdefault('preview', __incpy__.vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', __incpy__.internal.tab.getCurrent())
        self.view = __incpy__.view(kwds.pop('buffer', None) or __incpy__.vim.gvars['incpy#WindowName'], opt, **kwds)

    def write(self, data):
        """Writes data directly into view"""
        return self.view.write(data)

    def __repr__(self):
        if self.view.window > -1:
            return "<__incpy__.{:s} buffer:{:d}>".format(self.__class__.__name__, self.view.buffer.number)
        return "<__incpy__.{:s} buffer:{:d} hidden>".format(self.__class__.__name__, self.view.buffer.number)

    def attach(self):
        """Attaches interpreter to view"""
        raise __incpy__.builtins.NotImplementedError

    def detach(self):
        """Detaches interpreter from view"""
        raise __incpy__.builtins.NotImplementedError

    def communicate(self, command, silent=False):
        """Sends commands to interpreter"""
        raise __incpy__.builtins.NotImplementedError

    def start(self):
        """Starts the interpreter"""
        raise __incpy__.builtins.NotImplementedError

    def stop(self):
        """Stops the interpreter"""
        raise __incpy__.builtins.NotImplementedError
__incpy__.interpreter = interpreter; del(interpreter)

class interpreter_python_internal(__incpy__.interpreter):
    state = None

    def attach(self):
        sys, logging, logger = __incpy__.sys, __import__('logging'), __incpy__.logger
        self.state = sys.stdin, sys.stdout, sys.stderr, logger

        # notify the user
        logger.debug("redirecting sys.stdin, sys.stdout, and sys.stderr to {!r}".format(self.view))

        # add a handler for python output window so that it catches everything
        res = logging.StreamHandler(self.view)
        res.setFormatter(logging.Formatter(logging.BASIC_FORMAT, None))
        logger.root.addHandler(res)

        _, sys.stdout, sys.stderr = None, self.view, self.view

    def detach(self):
        if self.state is None:
            logger = __import__('logging').getLogger('incpy').getChild('vim')
            logger.fatal("refusing to detach internal interpreter as it was already previously detached")
            return

        sys, logging = __incpy__ and __incpy__.sys or __import__('sys'), __import__('logging')
        _, _, err, logger = self.state

        # remove the python output window formatter from the root logger
        logger.debug("removing window handler from root logger")
        try:
            logger.root.removeHandler(__incpy__.six.next(L for L in logger.root.handlers if isinstance(L, logging.StreamHandler) and type(L.stream).__name__ == 'view'))
        except StopIteration:
            pass

        logger.warning("detaching internal interpreter from sys.stdin, sys.stdout, and sys.stderr.")

        # notify the user that we're restoring the original state
        logger.debug("restoring sys.stdin, sys.stdout, and sys.stderr from: {!r}".format(self.state))
        (sys.stdin, sys.stdout, sys.stderr, _), self.state = self.state, None

    def communicate(self, data, silent=False):
        echonewline = __incpy__.vim.gvars['incpy#EchoNewline']
        if __incpy__.vim.gvars['incpy#Echo'] and not silent:
            echoformat = __incpy__.vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            trimmed = sum(1 for item in reversed(lines) if not item.strip())
            echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            self.write(echonewline.format(echo))
        __incpy__.six.exec_(data, __incpy__.builtins.globals())

    def start(self):
        __incpy__.logger.warning("internal interpreter has already been (implicitly) started")

    def stop(self):
        __incpy__.logger.fatal("unable to stop internal interpreter as it is always running")
__incpy__.interpreter_python_internal = interpreter_python_internal; del(interpreter_python_internal)

# external interpreter (newline delimited)
class interpreter_external(__incpy__.interpreter):
    instance = None

    @__incpy__.builtins.classmethod
    def new(cls, command, **options):
        res = cls(**options)
        [ options.pop(item, None) for item in cls.view_options ]
        res.command, res.options = command, options
        return res

    def attach(self):
        logger, = __incpy__.logger,

        logger.debug("connecting i/o from {!r} to {!r}".format(self.command, self.view))
        self.instance = __incpy__.spawn(self.view.write, self.command, **self.options)
        logger.info("started process {:d} ({:#x}): {:s}".format(self.instance.id, self.instance.id, self.command))

        self.state = logger,

    def detach(self):
        logger, = self.state
        if not self.instance:
            logger.fatal("refusing to detach external interpreter as it was already previous detached")
            return
        if not self.instance.running:
            logger.fatal("refusing to stop already terminated process {!r}".format(self.instance))
            self.instance = None
            return
        logger.info("killing process {!r}".format(self.instance))
        self.instance.stop()

        logger.debug("disconnecting i/o for {!r} from {!r}".format(self.instance, self.view))
        self.instance = None

    def communicate(self, data, silent=False):
        echonewline = __incpy__.vim.gvars['incpy#EchoNewline']
        if __incpy__.vim.gvars['incpy#Echo'] and not silent:
            echoformat = __incpy__.vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            trimmed = sum(1 for item in reversed(lines) if not item.strip())
            echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            self.write(echonewline.format(echo))
        self.instance.write(data)

    def __repr__(self):
        res = __incpy__.builtins.super(__incpy__.interpreter_external, self).__repr__()
        if self.instance.running:
            return "{:s} {{{!r} {:s}}}".format(res, self.instance, self.command)
        return "{:s} {{{!s}}}".format(res, self.instance)

    def start(self):
        __incpy__.logger.info("starting process {!r}".format(self.instance))
        self.instance.start()

    def stop(self):
        __incpy__.logger.info("stopping process {!r}".format(self.instance))
        self.instance.stop()
__incpy__.interpreter_external = interpreter_external; del(interpreter_external)

# terminal interpreter
class interpreter_terminal(__incpy__.interpreter_external):
    instance = None

    # hacked this in because i'm not sure what interpreter_external is supposed to be doing
    @property
    def options(self):
        return self.__options
    @options.setter
    def options(self, dict):
        self.__options.update(dict)

    def __init__(self, **kwds):
        self.__options = {'hidden': True}
        opt = {}.__class__(__incpy__.vim.gvars['incpy#CoreWindowOptions'])
        opt.update(__incpy__.vim.gvars['incpy#WindowOptions'])
        opt.update(kwds.pop('opt', {}))
        self.__options.update(opt)

        kwds.setdefault('preview', __incpy__.vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', __incpy__.internal.tab.getCurrent())
        self.__keywords = kwds
        #self.__view = None
        self.buffer = None

    @property
    def view(self):
        #if self.__view:
        #    return self.__view
        current = __incpy__.internal.window.current()
        #__incpy__.internal.window.select(__incpy__.vim.gvars['incpy#WindowName'])
        #__incpy__.vim.command('terminal ++open ++noclose ++curwin')
        buffer = self.start() if self.buffer is None else self.buffer
        self.__view = res = __incpy__.view(buffer, self.options, **self.__keywords)
        __incpy__.internal.window.select(current)
        return res

    def attach(self):
        """Attaches interpreter to view"""
        view = self.view
        window = view.window
        current = __incpy__.internal.window.current()

        # search to see if window exists, if it doesn't..then show it.
        searched = __incpy__.internal.window.buffer(self.buffer)
        if searched < 0:
            self.view.buffer = self.buffer

        __incpy__.internal.window.select(current)
        # do nothing, always attached

    def detach(self):
        """Detaches interpreter from view"""
        # do nothing, always attached

    def communicate(self, data, silent=False):
        """Sends commands to interpreter"""
        echonewline = __incpy__.vim.gvars['incpy#EchoNewline']
        if __incpy__.vim.gvars['incpy#Echo'] and not silent:
            echoformat = __incpy__.vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            trimmed = sum(1 for item in reversed(lines) if not item.strip())

            # Terminals don't let you modify or edit the buffer in any way
            #echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            #self.write(echonewline.format(echo))

        term_sendkeys = __incpy__.vim.Function('term_sendkeys')
        buffer = self.view.buffer
        term_sendkeys(buffer.number, data)

    def start(self):
        """Starts the interpreter"""
        term_start = __incpy__.vim.Function('term_start')

        # because python is maintained by fucking idiots
        ignored_env = {'PAGER', 'MANPAGER'}
        filtered_env = {name : '' if name in ignored_env else value for name, value in __import__('os').environ.items() if name not in ignored_env}
        filtered_env['TERM'] = 'emacs'

        options = vim.Dictionary({
            "hidden": 1,
            "stoponexit": 'term',
            "term_name": __incpy__.vim.gvars['incpy#WindowName'],
            "term_kill": 'hup',
            "term_finish": "open",
            # "env": vim.Dictionary(filtered_env),  # because VIM doesn't do as it's told
        })
        self.buffer = res = term_start(self.command, options)
        return res

    def stop(self):
        """Stops the interpreter"""
        term_getjob = __incpy__.vim.Function('term_getjob')
        job = term_getjob(self.buffer)

        job_stop = __incpy__.vim.Function('job_stop')
        job_stop(job)

        job_status = __incpy__.vim.Function('job_status')
        if job_status(job) != 'dead':
            raise builtins.Exception("Unable to terminate job {:d}".format(job))
        return
__incpy__.interpreter_terminal = interpreter_terminal; del(interpreter_terminal)

# vim internal
class internal(object):
    """Commands that interface with vim directly"""

    class tab(object):
        """Internal vim commands for interacting with tabs"""
        goto = __incpy__.builtins.staticmethod(lambda n: __incpy__.vim.command("tabnext {:d}".format(1 + n)))
        close = __incpy__.builtins.staticmethod(lambda n: __incpy__.vim.command("tabclose {:d}".format(1 + n)))
        #def move(n, t):    # FIXME
        #    current = int(__incpy__.vim.eval('tabpagenr()'))
        #    _ = t if current == n else current if t > current else current + 1
        #    __incpy__.vim.command("tabnext {:d} | tabmove {:d} | tabnext {:d}".format(1 + n, t, _))

        getCurrent = __incpy__.builtins.staticmethod(lambda: __incpy__.builtins.int(__incpy__.vim.eval('tabpagenr()')) - 1)
        getCount = __incpy__.builtins.staticmethod(lambda: __incpy__.builtins.int(__incpy__.vim.eval('tabpagenr("$")')))
        getBuffers = __incpy__.builtins.staticmethod(lambda n: [ __incpy__.builtins.int(item) for item in __incpy__.vim.eval("tabpagebuflist({:d})".format(n - 1)) ])

        getWindowCurrent = __incpy__.builtins.staticmethod(lambda n: __incpy__.builtins.int(__incpy__.vim.eval("tabpagewinnr({:d})".format(n - 1))))
        getWindowPrevious = __incpy__.builtins.staticmethod(lambda n: __incpy__.builtins.int(__incpy__.vim.eval("tabpagewinnr({:d}, '#')".format(n - 1))))
        getWindowCount = __incpy__.builtins.staticmethod(lambda n: __incpy__.builtins.int(__incpy__.vim.eval("tabpagewinnr({:d}, '$')".format(n - 1))))

    class buffer(object):
        """Internal vim commands for getting information about a buffer"""
        name = __incpy__.builtins.staticmethod(lambda id: __incpy__.builtins.str(__incpy__.vim.eval("bufname({!s})".format(id))))
        number = __incpy__.builtins.staticmethod(lambda id: __incpy__.builtins.int(__incpy__.vim.eval("bufnr({!s})".format(id))))
        window = __incpy__.builtins.staticmethod(lambda id: __incpy__.builtins.int(__incpy__.vim.eval("bufwinnr({!s})".format(id))))
        exists = __incpy__.builtins.staticmethod(lambda id: __incpy__.builtins.bool(__incpy__.vim.eval("bufexists({!s})".format(id))))

    class window(object):
        """Internal vim commands for doing things with a window"""

        # ui position conversion
        @__incpy__.builtins.staticmethod
        def positionToLocation(position):
            if position in {'left', 'above'}:
                return 'leftabove'
            if position in {'right', 'below'}:
                return 'rightbelow'
            raise __incpy__.builtins.ValueError(position)

        @__incpy__.builtins.staticmethod
        def positionToSplit(position):
            if position in {'left', 'right'}:
                return 'vsplit'
            if position in {'above', 'below'}:
                return 'split'
            raise __incpy__.builtins.ValueError(position)

        @__incpy__.builtins.staticmethod
        def optionsToCommandLine(options):
            builtins = __incpy__.builtins
            result = []
            for k, v in __incpy__.six.iteritems(options):
                if builtins.isinstance(v, __incpy__.six.string_types):
                    result.append("{:s}={:s}".format(k, v))
                elif builtins.isinstance(v, builtins.bool):
                    result.append("{:s}{:s}".format('' if v else 'no', k))
                elif builtins.isinstance(v, __incpy__.six.integer_types):
                    result.append("{:s}={:d}".format(k, v))
                else:
                    raise NotImplementedError(k, v)
                continue
            return '\\ '.join(result)

        # window selection
        @__incpy__.builtins.staticmethod
        def current():
            '''return the current window number'''
            return __incpy__.builtins.int(__incpy__.vim.eval('winnr()'))

        @__incpy__.builtins.staticmethod
        def select(window):
            '''Select the window with the specified window number'''
            return (__incpy__.builtins.int(__incpy__.vim.eval('winnr()')), __incpy__.vim.command("{:d} wincmd w".format(window)))[0]

        @__incpy__.builtins.staticmethod
        def currentsize(position):
            builtins = __incpy__.builtins
            if position in ('left', 'right'):
                return builtins.int(__incpy__.vim.eval('&columns'))
            if position in ('above', 'below'):
                return builtins.int(__incpy__.vim.eval('&lines'))
            raise builtins.ValueError(position)

        # properties
        @__incpy__.builtins.staticmethod
        def buffer(window):
            '''Return the bufferid for the specified window'''
            return __incpy__.builtins.int(__incpy__.vim.eval("winbufnr({:d})".format(window)))

        @__incpy__.builtins.staticmethod
        def available(bufferid):
            '''Return the first window number for a buffer id'''
            return __incpy__.builtins.int(__incpy__.vim.eval("bufwinnr({:d})".format(bufferid)))

        # window actions
        @__incpy__.builtins.classmethod
        def create(cls, bufferid, position, ratio, options, preview=False):
            '''create a window for the bufferid and return its number'''
            builtins = __incpy__.builtins
            last = cls.current()

            size = cls.currentsize(position) * ratio
            if preview:
                if builtins.len(options) > 0:
                    __incpy__.vim.command("noautocmd silent {:s} pedit! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), cls.optionsToCommandLine(options), __incpy__.internal.buffer.name(bufferid)))
                else:
                    __incpy__.vim.command("noautocmd silent {:s} pedit! {:s}".format(cls.positionToLocation(position), __incpy__.internal.buffer.name(bufferid)))
            else:
                if builtins.len(options) > 0:
                    __incpy__.vim.command("noautocmd silent {:s} {:d}{:s}! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), builtins.int(size), cls.positionToSplit(position), cls.optionsToCommandLine(options), __incpy__.internal.buffer.name(bufferid)))
                else:
                    __incpy__.vim.command("noautocmd silent {:s} {:d}{:s}! {:s}".format(cls.positionToLocation(position), builtins.int(size), cls.positionToSplit(position), __incpy__.internal.buffer.name(bufferid)))

            # grab the newly created window
            new = cls.current()
            try:
                if builtins.bool(__incpy__.vim.gvars['incpy#WindowPreview']):
                    return new

                newbufferid = cls.buffer(new)
                if bufferid > 0 and newbufferid == bufferid:
                    return new

                # if the bufferid doesn't exist, then we have to recreate one.
                if __incpy__.vim.eval("bufnr({:d})".format(bufferid)) < 0:
                    raise Exception("The requested buffer ({:d}) does not exist and will need to be created.".format(bufferid))

                # if our new bufferid doesn't match the requested one, then we switch to it.
                elif newbufferid != bufferid:
                    __incpy__.vim.command("buffer {:d}".format(bufferid))
                    __incpy__.logger.debug("Adjusted buffer ({:d}) for window {:d} to point to the correct buffer id ({:d})".format(newbufferid, new, bufferid))

            finally:
                cls.select(last)
            return new

        @__incpy__.builtins.classmethod
        def show(cls, bufferid, position, ratio, options, preview=False):
            '''return the window for the bufferid, recreating it if its now showing'''
            window = cls.available(bufferid)

            # if we already have a windowid for the buffer, then we can return it. otherwise
            # we rec-reate the window which should get the buffer to work.
            return window if window > 0 else cls.create(bufferid, position, ratio, options, preview=preview)

        @__incpy__.builtins.classmethod
        def hide(cls, bufferid, preview=False):
            last = cls.select(cls.buffer(bufferid))
            if preview:
                __incpy__.vim.command("noautocmd silent pclose!")
            else:
                __incpy__.vim.command("noautocmd silent close!")
            return cls.select(last)

        # window state
        @__incpy__.builtins.classmethod
        def saveview(cls, bufferid):
            last = cls.select( cls.buffer(bufferid) )
            res = __incpy__.vim.eval('winsaveview()')
            cls.select(last)
            return res

        @__incpy__.builtins.classmethod
        def restview(cls, bufferid, state):
            do = __incpy__.vim.Function('winrestview')
            last = cls.select( cls.buffer(bufferid) )
            do(state)
            cls.select(last)

        @__incpy__.builtins.classmethod
        def savesize(cls, bufferid):
            last = cls.select( cls.buffer(bufferid) )
            w, h = __incpy__.builtins.map(__incpy__.vim.eval, ['winwidth(0)', 'winheight(0)'])
            cls.select(last)
            return { 'width':w, 'height':h }

        @__incpy__.builtins.classmethod
        def restsize(cls, bufferid, state):
            window = cls.buffer(bufferid)
            return "vertical {:d} resize {:d} | {:d} resize {:d}".format(window, state['width'], window, state['height'])

__incpy__.internal = internal; del(internal)

# view -- window <-> buffer
class view(object):
    """This represents the window associated with a buffer."""

    def __init__(self, buffer, opt, preview, tab=None):
        """Create a view for the specified buffer.

        Buffer can be an existing buffer, an id number, filename, or even a new name.
        """
        self.options = opt
        self.preview = preview

        # Get the vim.buffer from the buffer the caller gave us.
        try:
            buf = __incpy__.buffer.of(buffer)

        # If we couldn't find the desired buffer, then we'll just create one
        # with the name that we were given.
        except Exception as E:

            # Create a buffer with the specified name. This is not really needed
            # as we're only creating it to sneak off with the buffer's name.
            if isinstance(buffer, __incpy__.six.string_types):
                buf = __incpy__.buffer.new(buffer)
            elif isinstance(buffer, __incpy__.six.integer_types):
                buf = __incpy__.buffer.new(__incpy__.vim.gvars['incpy#WindowName'])
            else:
                raise __incpy__.incpy.vim.error("Unable to determine output buffer name from parameter : {!r}".format(buffer))

        # Now we can grab the buffer's name so that we can use it to re-create
        # the buffer if it was deleted by the user.
        self.__buffer_name = buf.number
        #res = "'{!s}'".format(buf.name.replace("'", "''"))
        #self.__buffer_name = __incpy__.vim.eval("fnamemodify({:s}, \":.\")".format(res))

    @property
    def buffer(self):
        name = self.__buffer_name

        # Find the buffer by the name that was previously cached.
        try:
            result = __incpy__.buffer.of(name)

        # If we got an exception when trying to snag the buffer by its name, then
        # log the exception and create a new one to take the old one's place.
        except __incpy__.incpy.vim.error as E:
            __incpy__.logger.info("recreating output buffer due to exception : {!s}".format(E), exc_info=True)

            # Create a new buffer using the name that we expect it to have.
            if isinstance(name, __incpy__.six.string_types):
                result = __incpy__.buffer.new(name)
            elif isinstance(name, __incpy__.six.integer_types):
                result = __incpy__.buffer.new(__incpy__.vim.gvars['incpy#WindowName'])
            else:
                raise __incpy__.incpy.vim.error("Unable to determine output buffer name from parameter : {!r}".format(name))

        # Return the buffer we found back to the caller.
        return result
    @buffer.setter
    def buffer(self, number):
        id = __incpy__.vim.eval("bufnr({:d})".format(number))
        name = __incpy__.vim.eval("bufname({:d})".format(id))
        if id < 0:
            raise __incpy__.incpy.vim.error("Unable to locate buffer id from parameter : {!r}".format(number))
        elif not name:
            raise __incpy__.incpy.vim.error("Unable to determine output buffer name from parameter : {!r}".format(number))
        self.__buffer_name = id

    @property
    def window(self):
        result = self.buffer
        return __incpy__.internal.window.buffer(result.number)

    def write(self, data):
        """Write data directly into window contents (updating buffer)"""
        result = self.buffer
        return result.write(data)

    # Methods wrapping the window visibility and its scope
    def create(self, position, ratio):
        """Create window for buffer"""
        builtins, buffer = __incpy__.builtins, self.buffer

        # FIXME: creating a view in another tab is not supported yet
        if __incpy__.internal.buffer.number(buffer.number) == -1:
            raise builtins.Exception("Buffer {:d} does not exist".format(buffer.number))
        if 1.0 <= ratio < 0.0:
            raise builtins.Exception("Specified ratio is out of bounds {!r}".format(ratio))

        # create the window, get its buffer, and update our state with it.
        window = __incpy__.internal.window.create(buffer.number, position, ratio, self.options, preview=self.preview)
        self.buffer = __incpy__.vim.eval("winbufnr({:d})".format(window))
        return window

    def show(self, position, ratio):
        """Show window at the specified position if it is not already showing."""
        builtins, buffer = __incpy__.builtins, self.buffer

        # FIXME: showing a view in another tab is not supported yet
        # if buffer does not exist then recreate the fucker
        if __incpy__.internal.buffer.number(buffer.number) == -1:
            raise builtins.Exception("Buffer {:d} does not exist".format(buffer.number))
        # if __incpy__.internal.buffer.window(buffer.number) != -1:
        #    raise builtins.Exception("Window for {:d} is already showing".format(buffer.number))

        window = __incpy__.internal.window.show(buffer.number, position, ratio, self.options, preview=self.preview)
        self.buffer = __incpy__.vim.eval("winbufnr({:d})".format(window))
        return window

    def hide(self):
        """Hide the window"""
        builtins, buffer = __incpy__.builtins, buffer, self.buffer

        # FIXME: hiding a view in another tab is not supported yet
        if __incpy__.internal.buffer.number(buffer.number) == -1:
            raise builtins.Exception("Buffer {:d} does not exist".format(buffer.number))
        if __incpy__.internal.buffer.window(buffer.number) == -1:
            raise builtins.Exception("Window for {:d} is already hidden".format(buffer.number))

        return __incpy__.internal.window.hide(buffer.number, preview=self.preview)

    def __repr__(self):
        name = self.buffer.name
        descr = "{:d}".format(name) if isinstance(name, __incpy__.six.integer_types) else "\"{:s}\"".format(name)
        identity = descr if __incpy__.buffer.exists(self.__buffer_name) else "(missing) {:s}".format(descr)
        if self.preview:
            return "<__incpy__.view buffer:{:d} {:s} preview>".format(self.window, identity)
        return "<__incpy__.view buffer:{:d} {:s}>".format(self.window, identity)
__incpy__.view = view; del(view)

# spawn interpreter requested by user
_ = __incpy__.vim.gvars["incpy#Program"]
opt = {'winfixwidth':True, 'winfixheight':True} if __incpy__.vim.gvars["incpy#WindowFixed"] > 0 else {}
try:
    if __incpy__.vim.eval('has("terminal")') and len(_) > 0:
        __incpy__.cache = __incpy__.interpreter_terminal.new(_, opt=opt)
    elif len(_) > 0:
        __incpy__.cache = __incpy__.interpreter_external.new(_, opt=opt)
    else:
        __incpy__.cache = __incpy__.interpreter_python_internal.new(opt=opt)

except Exception:
    __incpy__.logger.fatal("error starting external interpreter: {:s}".format(_), exc_info=True)
    __incpy__.logger.warning("falling back to internal python interpreter")
    __incpy__.cache = __incpy__.interpreter_python_internal.new(opt=opt)
del(opt)

# create it's window, and store the buffer's id
view = __incpy__.cache.view
__incpy__.vim.gvars['incpy#BufferId'] = view.buffer.number
view.create(__incpy__.vim.gvars['incpy#WindowPosition'], __incpy__.vim.gvars['incpy#WindowRatio'])

# delete our temp variable
del(view)

EOF
endfunction

""" Plugin management interface
function! incpy#Start()
    " Start the target program and attach it to a buffer
    pythonx __incpy__.cache.start()
endfunction

function! incpy#Stop()
    " Stop the target program and detach it from its buffer
    pythonx __incpy__.cache.stop()
endfunction

function! incpy#Restart()
    " Restart the target program
    pythonx __incpy__.cache.stop()
    pythonx __incpy__.cache.start()
endfunction

""" Plugin interaction interface
function! incpy#Show()
    execute "pythonx __incpy__.cache.view.show(__incpy__.vim.gvars['incpy#WindowPosition'], __incpy__.vim.gvars['incpy#WindowRatio'])"
endfunction

function! incpy#Hide()
    execute "pythonx __incpy__.cache.view.hide()"
endfunction

function! incpy#Execute(line)
    call incpy#Show()
    execute printf("pythonx __incpy__.cache.communicate('%s')", escape(a:line, "'\\"))
    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#Range(begin, end)
    " Execute the specified lines in the target
    let lines = getline(a:begin, a:end)
    let stripped = s:strip_by_option(g:incpy#InputStrip, lines)

    " Execute the lines in our target
    let code = join(map(stripped, 'escape(v:val, "''\\")'), "\\n")
    let code_stripped = s:strip_by_option(g:incpy#ExecStrip, code)
    call incpy#Show()
    execute printf("pythonx (lambda code=\"%s\".format(\"%s\"): __incpy__.cache.communicate(code))()", s:singleline(g:incpy#ExecFormat, "\"\\"), escape(code_stripped, "\""))

    " If the user configured us to follow the output, then do as we were told.
    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#Evaluate(expr)
    let stripped = s:strip_by_option(g:incpy#EvalStrip, a:expr)
    let encoded = substitute(printf("(%s)", stripped), '.', '\=printf("\\x%02x", char2nr(submatch(0)))', 'g')

    " Evaluate and emit an expression in the target using the plugin
    call incpy#Show()
    execute printf("pythonx (lambda code=\"%s\".format(\"%s\"): __incpy__.cache.communicate(code))()", s:singleline(g:incpy#EvalFormat, "\"\\"), encoded)

    if g:incpy#OutputFollow
        try | call s:windowtail(g:incpy#BufferId) | catch /^Invalid/ | endtry
    endif
endfunction

function! incpy#Halp(expr)
    " Remove all encompassing whitespace from expression
    let LetMeSeeYouStripped = substitute(a:expr, '^[ \t\n]\+\|[ \t\n]\+$', '', 'g')

    " Execute g:incpy#HelpFormat in the target using the plugin's cached communicator
    call incpy#Show()
    execute printf("pythonx (lambda code=\"%s\".format(\"%s\"): __incpy__.cache.communicate(code))()", s:singleline(g:incpy#HelpFormat, "\"\\"), escape(LetMeSeeYouStripped, "\"\\"))
endfunction

""" Actual execution and setup of the plugin
    let s:current_script=expand("<sfile>:p:h")
    call incpy#SetupOptions()
    call incpy#SetupPython(s:current_script)
    call incpy#Setup()
    call incpy#SetupCommands()
    call incpy#SetupKeys()

    " if we're using an external program, then there's no dotfile we need to seed with.
    if g:incpy#Program == ""
        call incpy#ImportDotfile()
    endif

    " on entry, silently import the user module to honor any user-specific configurations
    autocmd VimEnter * pythonx hasattr(__incpy__, 'cache') and __incpy__.cache.attach()
    autocmd VimLeavePre * pythonx hasattr(__incpy__, 'cache') and __incpy__.cache.detach()

    " if greenlets were specifed then make sure to update them during cursor movement
    if g:incpy#Greenlets
        autocmd CursorHold * pythonx __import__('gevent').idle(0.0)
        autocmd CursorHoldI * pythonx __import__('gevent').idle(0.0)
        autocmd CursorMoved * pythonx __import__('gevent').idle(0.0)
        autocmd CursorMovedI * pythonx __import__('gevent').idle(0.0)
    endif

else
    echoerr "Vim compiled without +python support. Unable to initialize plugin from ". expand("<sfile>")
endif
