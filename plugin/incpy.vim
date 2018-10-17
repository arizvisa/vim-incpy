" based on an idea that bniemczyk@gmail.com had
" thanks to ccliver@gmail.org for his input
" thanks to Tim Pope <vimNOSPAM@tpope.info> for pointing out preview windows
"
" requires vim to be compiled w/ python support. I noticed that most of my
" python development consisted of copying code into the python interpreter
" FIXME: i deleted this line during some time
" required by copy&paste, I decided to make vim more friendly for that style
" of development. this is the result. I apologize for the hackiness.
"
" when a .py file is opened (determined by filetype), a buffer is created
"
" python-output
" this contains the output of all the code you've executed.
" by default this is shown in a splitscreened window
"
" Usage:
" Move the cursor to a line or hilight some text (visual mode)
" and hit '!' to execute in the python interpreter. it's output will
" be displayed in 'python-output'
"
" ! -- execute current selected row
" Ctrl+@ -- display repr for symbol under character
" Ctrl+_ -- display help for symbol under character
"
" Installation:
" If in posix, copy to ~/.vim/plugin/
" If in windows, copy to $USERPROFILE/vimfiles/plugin/
"
" basic knowledge of window management is required to use effectively. here's
" a quickref:
"
"   <C-w>s -- horizontal split
"   <C-w>v -- vertical split
"   <C-w>o -- hide all other windows
"   <C-w>q -- close current window
"   <C-w>{h,l,j,k} -- move to the window left,right,down,up from current one
"
" Configuration (via globals):
" string g:incpy#Program      -- name of subprogram (if empty, use vim's internal python)
" int    g:incpy#Greenlets    -- whether to use greenlets (lightweight-threads) or not.
" int    g:incpy#OutputFollow -- go to the end of output when input is sent
" string g:incpy#InputFormat  -- when executing a command, what to terminate it with
" int    g:incpy#InputStrip   -- whether to strip leading indent
" int    g:incpy#Echo         -- whether the plugin should echo all input to the program
" string g:incpy#EchoFormat   -- the formatspec to execute each line with
"
" string g:incpy#WindowName     -- the name of the output buffer that gets created.
" int    g:incpy#WindowFixed    -- don't allow automatic resizing of the window
" dict   g:incpy#WindowOptions  -- new window options
" int    g:incpy#WindowPreview  -- use preview windows
" string g:incpy#WindowPosition -- window position.  ['above', 'below', 'left', 'right']
" float  g:incpy#WindowRatio    -- window size on creation
"
" Todo:
"       the auto-popup of the buffer based on the filetype was pretty cool
"       if some of the Program output is parsed, it might be possible to
"           create a fold labelled by the first rw python code that
"           exec'd it
"       maybe exeecution of the contents of a register would be useful
"       verify everything is cool in the linux-world

if has("python")

" vim string manipulation for indents and things
function! s:count_indent(string)
    " count the beginning whitespace of a string
    let characters = 0
    for c in split(a:string,'\zs')
        if stridx(" \t",c) == -1
            break
        endif
        let characters += 1
    endfor
    return characters
endfunction

function! s:find_common_indent(lines)
    " find the smallest indent
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

function! s:strip_indentation(lines)
    let indentsize = s:find_common_indent(a:lines)

    " remove the indent
    let results = []
    let prevlength = 0
    for l in a:lines
        if strlen(l) == 0
            let row = repeat(" ",prevlength)
        else
            let row = strpart(l,indentsize)
            let prevlength = s:count_indent(row)
        endif
        let results += [row]
    endfor
    return results
endfunction

function! s:selected() range
    " really, vim? really??
    let oldvalue = getreg("")
    normal gvy
    let result = getreg("")
    call setreg("", oldvalue)
    return result
endfunction

"" private window management
function! s:windowselect(id)
    " select the requested windowid, return the previous window id
    let current = winnr()
    execute printf("%d wincmd w", a:id)
    return current
endfunction

function! s:windowtail(bufid)
    " tail the window with the requested bufid
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
            if index(tabpagebuflist(tn+1), a:bufid) > -1
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

function! incpy#Start()
    python __incpy__.cache.start()
endfunction

function! incpy#Stop()
    python __incpy__.cache.stop()
endfunction

function! incpy#Restart()
    python __incpy__.cache.stop()
    python __incpy__.cache.start()
endfunction

" incpy methods
function! incpy#SetupPython(currentscriptpath)
    let m = substitute(a:currentscriptpath, "\\", "/", "g")

    " FIXME: use sys.meta_path

    " setup the default logger
    python __import__('logging').basicConfig()
    python __import__('logging').getLogger('incpy')

    " add the python path using the runtimepath directory that this script is contained in
    for p in split(&runtimepath,",")
        let p = substitute(p, "\\", "/", "g")
        if stridx(m, p, 0) == 0
            execute printf("python __import__('sys').path.append('%s/python')", p)
            return
        endif
    endfor

    " otherwise, look up from our current script's directory for a python sub-directory
    let p = finddir("python", m . ";")
    if isdirectory(p)
        execute printf("python __import__('sys').path.append('%s')", p)
        return
    endif

    throw printf("Unable to determine basepath from script %s", m)
endfunction

""" external interfaces
function! incpy#Execute(line)
    execute printf("python __incpy__.cache.communicate('%s')", escape(a:line, "'\\"))
    if g:incpy#OutputFollow
        call s:windowtail(g:incpy#BufferId)
    endif
endfunction
function! incpy#Range(begin,end)
    let lines = getline(a:begin,a:end)
    if g:incpy#InputStrip
        let lines = s:strip_indentation(lines)
    endif

    let code_s = join(map(lines, 'escape(v:val, "''\\")'), "\\n")
    execute printf("python __incpy__.cache.communicate('%s')", code_s)
    if g:incpy#OutputFollow
        call s:windowtail(g:incpy#BufferId)
    endif
endfunction
function! incpy#Evaluate(expr)
    "execute printf("python __incpy__.cache.communicate('_=%s;print _')", escape(a:expr, "'\\"))
    "execute printf("python __incpy__.cache.communicate('__incpy__.sys.displayhook(%s)')", escape(a:expr, "'\\"))
    "execute printf("python __incpy__.cache.communicate('__incpy__.builtin._=%s;print __incpy__.__builtin__._')", escape(a:expr, "'\\"))
    let module = escape("__import__('__builtin__')", "'\\")
    execute printf("python __incpy__.cache.communicate('%s._=%s;print %s.repr(%s._)')", module, escape(a:expr, "'\\"), module, module)
    if g:incpy#OutputFollow
        call s:windowtail(g:incpy#BufferId)
    endif
endfunction
function! incpy#Halp(expr)
    let LetMeSeeYouStripped = substitute(a:expr, '^[ \t\n]\+\|[ \t\n]\+$', '', 'g')
    let module = escape("__import__('__builtin__')", "'\\")
    execute printf("python try:__incpy__.cache.communicate('%s.help(%s)')\nexcept __incpy__.builtin.SyntaxError:__incpy__.cache.communicate('%s.help(\\'%s\\')')", module, escape(LetMeSeeYouStripped, "'\\"), module, escape(LetMeSeeYouStripped, "'\\"))
endfunction

" Create vim commands
function! incpy#MapCommands()
    command PyLine call incpy#Range(line("."),line("."))
    command PyBuffer call incpy#Range(0,line('$'))

    command -nargs=1 Py call incpy#Execute(<q-args>)
    command -range PyRange call incpy#Range(<line1>,<line2>)

    " python-specific commands
    command -nargs=1 PyEval call incpy#Evaluate(<q-args>)
    command -range PyEvalRange <line1>,<line2>call incpy#Evaluate(s:selected())
    command -nargs=1 PyHelp call incpy#Halp(<q-args>)
    command -range PyHelpRange <line1>,<line2>call incpy#Halp(s:selected())
endfunction

" Setup key mappings
function! incpy#MapKeys()
    nmap ! :PyLine<C-M>
    vmap ! :PyRange<C-M>

    " python-specific mappings
    nmap <C-\> :call incpy#Evaluate(expand("<cword>"))<C-M>
    vmap <C-\> :PyEvalRange<C-M>
    nmap  :call incpy#Halp(expand("<cword>"))<C-M>
    vmap <C-_> :PyHelpRange<C-M>
endfunction

" Setup default options
function! incpy#SetupOptions()
    let defopts = {}
    let defopts["Program"] = ""
    let defopts["Greenlets"] = 0
    let defopts["Echo"] = 1
    let defopts["OutputFollow"] = 1
    let defopts["InputStrip"] = 1
    let defopts["WindowName"] = "Scratch"
    let defopts["WindowRatio"] = 1.0/3
    let defopts["WindowPosition"] = "below"
    let defopts["WindowOptions"] = {"buftype":"nowrite", "noswapfile":[], "updatecount":0, "nobuflisted":[], "filetype":"python"}
    let defopts["WindowPreview"] = 0
    let defopts["WindowFixed"] = 0

    for o in keys(defopts)
        if ! exists("g:incpy#{o}")
            let g:incpy#{o} = defopts[o]
        endif
    endfor
endfunction

" Setup python interface
function! incpy#Setup()
    " Set any the options for the python module part.
    if g:incpy#Greenlets > 0
        " If greenlets were specified, then enable it by importing 'gevent' into the current python environment
        python __import__('gevent')
    elseif g:incpy#Program != ""
        " Otherwise we only need to warn the user that they should use it if they're trying to run an external program
        echohl WarningMsg | echomsg "WARNING:incpy.vim:Using vim-incpy to run an external program without support for greenlets will be unstable" | echohl None
    endif

    " Initialize python __incpy__ namespace
    python <<EOF

# create a pseudo-builtin module
__incpy__ = __builtins__.__class__('__incpy__', 'Internal state module for vim-incpy')
__incpy__.sys,__incpy__.incpy,__incpy__.builtin = __import__('sys'),__import__('incpy'),__import__('__builtin__')
__incpy__.vim,__incpy__.buffer,__incpy__.spawn = __incpy__.incpy.vim,__incpy__.incpy.buffer,__incpy__.incpy.spawn

# save initial state
__incpy__.state = __incpy__.builtin.tuple((__incpy__.builtin.getattr(__incpy__.sys,_) for _ in ('stdin','stdout','stderr')))
__incpy__.logger = __import__('logging').getLogger('incpy').getChild('vim')

# interpreter classes
class interpreter(object):
    # options that are used for constructing the view
    view_options = ('buffer','opt','preview','tab')

    @__incpy__.builtin.classmethod
    def new(cls, **options):
        options.setdefault('buffer', None)
        return cls(**options)
    def __init__(self, **kwds):
        opt = {}.__class__(__incpy__.vim.gvars['incpy#WindowOptions'])
        opt.update(kwds.pop('opt',{}))
        kwds.setdefault('preview', __incpy__.vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', __incpy__.internal.tab.getCurrent())
        self.view = __incpy__.view(kwds.pop('buffer',None) or __incpy__.vim.gvars['incpy#WindowName'], opt, **kwds)
    def __del__(self):
        return self.detach()
    def write(self, data):
        """Writes data directly into view"""
        return self.view.write(data)
    def __repr__(self):
        if self.view.window > -1:
            return "<__incpy__.{:s} buffer:{:d}>".format(self.__class__.__name__, self.view.buffer.number)
        return "<__incpy__.{:s} buffer:{:d} hidden>".format(self.__class__.__name__, self.view.buffer.number)

    def attach(self):
        """Attaches interpreter to view"""
        raise __incpy__.builtin.NotImplementedError
    def detach(self):
        """Detaches interpreter from view"""
        raise __incpy__.builtin.NotImplementedError
    def communicate(self, command, silent=False):
        """Sends commands to interpreter"""
        raise __incpy__.builtin.NotImplementedError
    def start():
        """Starts the interpreter"""
        raise __incpy__.builtin.NotImplementedError
    def stop():
        """Stops the interpreter"""
        raise __incpy__.builtin.NotImplementedError
__incpy__.interpreter = interpreter; del(interpreter)

class interpreter_python_internal(__incpy__.interpreter):
    state = None
    def attach(self):
        sys, logging, logger = __incpy__.sys, __import__('logging'), __incpy__.logger
        self.state = sys.stdin,sys.stdout,sys.stderr,logger

        # notify the user
        logger.debug("redirecting sys.{{stdin,stdout,stderr}} to {!r}".format(self.view))

        # add a handler for python output window so that it catches everything
        res = logging.StreamHandler(self.view)
        res.setFormatter(logging.Formatter(logging.BASIC_FORMAT, None))
        logger.root.addHandler(res)

        _,sys.stdout,sys.stderr = None,self.view,self.view
    def detach(self):
        if self.state is None: return

        sys, logging = __incpy__ and __incpy__.sys or __import__('sys'), __import__('logging')
        _, _, err, logger = self.state

        # notify the user
        logger.debug("restoring sys.{{stdin,stdout,stderr}} to {!r}".format(self.state))

        # remove the python output window formatter from the root logger
        try:
            logger.root.removeHandler(next(L for L in logger.root.handlers if isinstance(L, logging.StreamHandler) and type(L.stream).__name__ == 'view'))
        except StopIteration:
            pass

        sys.stdin,sys.stdout,sys.stderr,_ = self.state
    def communicate(self, data, silent=False):
        inputformat = __incpy__.vim.gvars.get('incpy#InputFormat', '{}\n')
        if __incpy__.vim.gvars['incpy#Echo'] and not silent:
            echoformat = __incpy__.vim.gvars.get('incpy#EchoFormat', "# >>> {}")
            echo = '\n'.join(map(echoformat.format, data.split('\n')))
            echo = inputformat.format(echo)
            self.view.write(echo)
        input = data
        exec input in __incpy__.builtin.globals()
    def start():
        __incpy__.logger.warn("vim's internal python interpreter has already been started")
    def stop():
        __incpy__.logger.fatal("refusing to stop vim's internal python interpreter")
__incpy__.interpreter_python_internal = interpreter_python_internal; del(interpreter_python_internal)

# external interpreter (newline delimited)
class interpreter_external(__incpy__.interpreter):
    instance = None
    @__incpy__.builtin.classmethod
    def new(cls, command, **options):
        res = cls(**options)
        __incpy__.builtin.map(lambda n,d=options:d.pop(n,None), cls.view_options)
        res.command,res.options = command,options
        return res
    def attach(self):
        __incpy__.logger.debug("connecting i/o from {!r} to {!r}".format(self.command, self.view))
        self.instance = __incpy__.spawn(self.view.write, self.command, **self.options)
        __incpy__.logger.info("started process {:d} ({:#x}): {:s}".format(self.instance.id,self.instance.id,self.command))
    def detach(self):
        if not self.instance:
            return
        if not self.instance.running:
            __incpy__.logger.fatal("refusing to stop already terminated process {!r}".format(self.instance))
            return
        __incpy__.logger.info("killing process {!r}".format(self.instance))
        self.instance.stop()
        __incpy__.logger.debug("disconnecting i/o for {!r} from {!r}".format(self.instance,self.view))
        self.instance = None

    def communicate(self, data, silent=False):
        inputformat = __incpy__.vim.gvars.get('incpy#InputFormat', '{}\n')
        if __incpy__.vim.gvars['incpy#Echo'] and not silent:
            echoformat = __incpy__.vim.gvars.get('incpy#EchoFormat', "{}")
            echo = echoformat.format(data)
            echo = inputformat.format(data)
            self.view.write(echo)
        input = inputformat.format(data)
        self.instance.write(input)
    def __repr__(self):
        res = __incpy__.builtin.super(__incpy__.interpreter_external, self).__repr__()
        if self.instance.running:
            return "{:s} {{{!r} {:s}}}".format(res, self.instance, self.command)
        return "{:s} {{{!s}}}".format(res, self.instance)
    def start():
        __incpy__.logger.info("starting process {!r}".format(self.instance))
        self.instance.start()
    def stop():
        __incpy__.logger.info("stopping process {!r}".format(self.instance))
        self.instance.stop()
__incpy__.interpreter_external = interpreter_external; del(interpreter_external)

# vim internal
class internal(object):
    """Commands that interface with vim directly"""
    class tab(object):
        """Internal vim commands for interacting with tabs"""
        goto = __incpy__.builtin.staticmethod(lambda n: __incpy__.vim.command("tabnext {:d}".format(n+1)))
        close = __incpy__.builtin.staticmethod(lambda n: __incpy__.vim.command("tabclose {:d}".format(n+1)))
        #def move(n, t):    # FIXME
        #    current = int(__incpy__.vim.eval('tabpagenr()'))
        #    _ = t if current == n else current if t > current else current+1
        #    __incpy__.vim.command("tabnext {:d} | tabmove {:d} | tabnext {:d}".format(n+1,t,_))

        getCurrent = __incpy__.builtin.staticmethod(lambda: __incpy__.builtin.int(__incpy__.vim.eval('tabpagenr()')) - 1)
        getCount = __incpy__.builtin.staticmethod(lambda: __incpy__.builtin.int(__incpy__.vim.eval('tabpagenr("$")')))
        getBuffers = __incpy__.builtin.staticmethod(lambda n: __incpy__.builtin.map(int,__incpy__.vim.eval("tabpagebuflist({:d})".format(n-1))))

        getWindowCurrent = __incpy__.builtin.staticmethod(lambda n: __incpy__.builtin.int(__incpy__.vim.eval("tabpagewinnr({:d})".format(n-1))))
        getWindowPrevious = __incpy__.builtin.staticmethod(lambda n: __incpy__.builtin.int(__incpy__.vim.eval("tabpagewinnr({:d}, '#')".format(n-1))))
        getWindowCount = __incpy__.builtin.staticmethod(lambda n: __incpy__.builtin.int(__incpy__.vim.eval("tabpagewinnr({:d}, '$')".format(n-1))))

    class buffer(object):
        """Internal vim commands for getting information about a buffer"""
        name = __incpy__.builtin.staticmethod(lambda id: __incpy__.builtin.str(__incpy__.vim.eval("bufname({:d})".format(id))))
        number = __incpy__.builtin.staticmethod(lambda id: __incpy__.builtin.int(__incpy__.vim.eval("bufnr({:d})".format(id))))
        window = __incpy__.builtin.staticmethod(lambda id: __incpy__.builtin.int(__incpy__.vim.eval("bufwinnr({:d})".format(id))))

    class window(object):
        """Internal vim commands for doing things with a window"""

        # ui position conversion
        @__incpy__.builtin.staticmethod
        def positionToLocation(position):
            if position in ('left','above'):
                return 'leftabove'
            if position in ('right','below'):
                return 'rightbelow'
            raise __incpy__.builtin.ValueError, position
        @__incpy__.builtin.staticmethod
        def positionToSplit(position):
            if position in ('left','right'):
                return 'vsplit'
            if position in ('above','below'):
                return 'split'
            raise __incpy__.builtin.ValueError, position
        @__incpy__.builtin.staticmethod
        def optionsToCommandLine(options):
            builtin = __incpy__.builtin
            result = []
            for k,v in options.iteritems():
                if builtin.isinstance(v, (int,long)):
                    result.append("{:s}={:d}".format(k,v))
                elif builtin.isinstance(v, basestring):
                    result.append("{:s}={:s}".format(k,v))
                else:
                    result.append(k)
                continue
            return '\\ '.join(result)

        # window selection
        @__incpy__.builtin.staticmethod
        def current():
            '''return the current window'''
            return __incpy__.builtin.int(__incpy__.vim.eval('winnr()'))
        @__incpy__.builtin.staticmethod
        def select(window):
            '''Select the window with the specified id'''
            return (__incpy__.builtin.int(__incpy__.vim.eval('winnr()')),__incpy__.vim.command("{:d} wincmd w".format(window)))[0]
        @__incpy__.builtin.staticmethod
        def currentsize(position):
            builtin = __incpy__.builtin
            if position in ('left','right'):
                return builtin.int(__incpy__.vim.eval('winwidth(0)'))
            if position in ('above','below'):
                return builtin.int(__incpy__.vim.eval('winheight(0)'))
            raise builtin.ValueError, position

        # properties
        @__incpy__.builtin.staticmethod
        def buffer(bufferid):
            '''Return the window according to the bufferid'''
            return __incpy__.builtin.int(__incpy__.vim.eval("winbufnr({:d})".format(bufferid)))

        # window actions
        @__incpy__.builtin.classmethod
        def create(cls, bufferid, position, size, options, preview=False):
            builtin = __incpy__.builtin
            last = cls.current()
            if preview:
                if builtin.len(options) > 0:
                    __incpy__.vim.command("noautocmd silent {:s} pedit! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), cls.optionsToCommandLine(options), __incpy__.internal.buffer.name(bufferid)))
                else:
                    __incpy__.vim.command("noautocmd silent {:s} pedit! {:s}".format(cls.positionToLocation(position), __incpy__.internal.buffer.name(bufferid)))
            else:
                if builtin.len(options) > 0:
                    __incpy__.vim.command("noautocmd silent {:s} {:d}{:s}! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), size, cls.positionToSplit(position), cls.optionsToCommandLine(options), __incpy__.internal.buffer.name(bufferid)))
                else:
                    __incpy__.vim.command("noautocmd silent {:s} {:d}{:s}! {:s}".format(cls.positionToLocation(position), size, cls.positionToSplit(position), __incpy__.internal.buffer.name(bufferid)))

            res = cls.current()
            cls.select(last)
            if not builtin.bool(__incpy__.vim.gvars['incpy#WindowPreview']):
                wid = cls.buffer(bufferid)
                if res != wid:
                    raise AssertionError("Newly created window is not pointing to the correct buffer id : {!r} != {!r}".format(wid, res))
            return res

        @__incpy__.builtin.classmethod
        def show(cls, bufferid, position, preview=False):
            last = cls.select( cls.buffer(bufferid) )
            if preview:
                __incpy__.vim.command("noautocmd silent {:s} pedit! {:s}".format(cls.positionToLocation(position), __incpy__.internal.buffer.name(bufferid)))
            else:
                __incpy__.vim.command("noautocmd silent {:s} {:s}! {:s}".format(cls.positionToLocation(position), cls.positionToSplit(position), __incpy__.internal.buffer.name(bufferid)))

            res = cls.current()
            cls.select(last)
            if res != cls.buffer(bufferid):
                raise AssertionError
            return res
        @__incpy__.builtin.classmethod
        def hide(cls, bufferid, preview=False):
            last = cls.select( cls.buffer(bufferid) )
            if preview:
                __incpy__.vim.command("noautocmd silent pclose!")
            else:
                __incpy__.vim.command("noautocmd silent close!")
            self.window = cls.buffer(bufferid)
            cls.select(last)

        # window state
        @__incpy__.builtin.classmethod
        def saveview(cls, bufferid):
            last = cls.select( cls.buffer(bufferid) )
            res = __incpy__.vim.eval('winsaveview()')
            cls.select(last)
            return res
        @__incpy__.builtin.classmethod
        def restview(cls, bufferid, state):
            do = __incpy__.vim.Function('winrestview')
            last = cls.select( cls.buffer(bufferid) )
            do(state)
            cls.select(last)
        @__incpy__.builtin.classmethod
        def savesize(cls, bufferid):
            last = cls.select( cls.buffer(bufferid) )
            w,h = __incpy__.builtin.map(__incpy__.vim.eval, ('winwidth(0)','winheight(0)'))
            cls.select(last)
            return { 'width':w, 'height':h }
        @__incpy__.builtin.classmethod
        def restsize(cls, bufferid, state):
            window = cls.buffer(bufferid)
            return "vertical {:d} resize {:d} | {:d} resize {:d}".format(window, state['width'], window, state['height'])

__incpy__.internal = internal; del(internal)

# view -- window <-> buffer
class view(object):
    """This represents the window associated with a buffer."""

    def __init__(self, buffer, opt, preview, tab=None):
        """Create a view for the specified buffer.

        Buffer can be an existing id number, filename, or new name.
        """
        self.buffer = self.__get_buffer(buffer)
        self.options = opt
        self.preview = preview
        self.window = __incpy__.internal.window.buffer( self.buffer.number )
        # FIXME: creating a view in another tab is not supported yet

    def __get_buffer(self, target):
        builtin = __incpy__.builtin
        if builtin.isinstance(target, int):
            return __incpy__.buffer.from_id(target)
        elif builtin.isinstance(target, basestring):
            try: return __incpy__.buffer.from_name(target)
            except: return __incpy__.buffer.new(target)
        raise __incpy__.incpy.error, "Unable to determine output buffer from parameter : {!r}".format(target)

    def write(self, data):
        """Write data directly into window contents (updating buffer)"""
        return self.buffer.write(data)

    def create(self, position, ratio):
        """Create window for buffer"""
        builtin = __incpy__.builtin
        buf = self.buffer
        if __incpy__.internal.buffer.number(buf.number) == -1:
            raise builtin.Exception, "Buffer {:d} does not exist".format(buf.number)
        if 1.0 <= ratio < 0.0:
            raise builtin.Exception, "Specified ratio is out of bounds {!r}".format(ratio)

        current = __incpy__.internal.window.current()
        sz = __incpy__.internal.window.currentsize(position) * ratio
        result = __incpy__.internal.window.create(buf.number, position, int(sz), self.options, preview=self.preview)
        self.window = result
        return result

    def show(self, position):
        """Show window at the specified position"""
        builtin = __incpy__.builtin
        buf = self.buffer
        if __incpy__.internal.buffer.number(buf.number) == -1:
            raise builtin.Exception, "Buffer {:d} does not exist".format(buf.number)
        if __incpy__.internal.buffer.window(buf.number) != -1:
            raise builtin.Exception, "Window for {:d} is already showing".format(buf.number)
        __incpy__.internal.window.show(buf.number, position, preview=self.preview)

    def hide(self):
        """Hide the window"""
        builtin = __incpy__.builtin
        buf = self.buffer
        if __incpy__.internal.buffer.number(buf.number) == -1:
            raise builtin.Exception, "Buffer {:d} does not exist".format(buf.number)
        if __incpy__.internal.buffer.window(buf.number) == -1:
            raise builtin.Exception, "Window for {:d} is already hidden".format(buf.number)
        __incpy__.internal.window.hide(buf.number, preview=self.preview)

    def __repr__(self):
        if self.preview:
            return "<__incpy__.view buffer:{:d} \"{:s}\" preview>".format(self.window, self.buffer.name)
        return "<__incpy__.view buffer:{:d} \"{:s}\">".format(self.window, self.buffer.name)
__incpy__.view = view; del(view)

# spawn interpreter requested by user
_ = __incpy__.vim.gvars["incpy#Program"]
opt = {'winfixwidth':True,'winfixheight':True} if __incpy__.vim.gvars["incpy#WindowFixed"]>0 else {}
try:
    __incpy__.cache = __incpy__.interpreter_external.new(_, opt=opt) if len(_) > 0 else __incpy__.interpreter_python_internal.new(opt=opt)
except:
    __incpy__.logger.fatal("error starting external interpreter: {:s}".format(_), exc_info=True)
    __incpy__.logger.warn("falling back to internal python interpreter")
    __incpy__.cache = __incpy__.interpreter_python_internal.new(opt=opt)
del(opt)

# create it's window, and store the buffer's id
_ = __incpy__.cache.view
__incpy__.vim.gvars['incpy#BufferId'] = _.buffer.number
_.create(__incpy__.vim.gvars['incpy#WindowPosition'], __incpy__.vim.gvars['incpy#WindowRatio'])

# delete our temp variable
del(_)

EOF
endfunction

    let s:current_script=expand("<sfile>:p:h")
    call incpy#SetupOptions()
    call incpy#SetupPython(s:current_script)
    call incpy#Setup()
    call incpy#MapCommands()
    call incpy#MapKeys()

    " on entry, silently import the user module to honor any user-specific configurations
    autocmd VimEnter * python hasattr(__incpy__,'cache') and __incpy__.cache.attach()
    autocmd VimLeavePre * python hasattr(__incpy__,'cache') and __incpy__.cache.detach()

    if g:incpy#Greenlets > 0
        autocmd CursorHold * python __import__('gevent').idle(0.0)
        autocmd CursorHoldI * python __import__('gevent').idle(0.0)
        autocmd CursorMoved * python __import__('gevent').idle(0.0)
        autocmd CursorMovedI * python __import__('gevent').idle(0.0)
    endif

else
    echoerr "Vim compiled without python support. Unable to initialize plugin from ". expand("<sfile>")
endif
