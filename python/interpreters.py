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
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)
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
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)
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
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)

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
            for k, v in options.items():
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

    # Create a fake descriptor that always returns the default encoding.
    class encoding_descriptor(object):
        def __init__(self):
            self.module = __import__('sys')
        def __get__(self, obj, type=None):
            return self.module.getdefaultencoding()
    encoding = encoding_descriptor()
    del(encoding_descriptor)

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
