import sys, functools, codecs
from . import integer_types, string_types, logger

logger = logger.getChild(__name__)

try:
    import vim as _vim

except ImportError:
    logger.warning('unable to import the vim module for python-vim. skipping the definition of its wrappers.')

# vim wrapper
else:
    class vim(object):
        try:
            import collections.abc as collections
        except ImportError:
            import collections

        class _autofixlist(collections.MutableMapping):
            def __init__(self, backing):
                self.__backing__ = backing
            def __len__(self):
                return len(self.__backing__)
            def __iter__(self):
                for item in self.__backing__:
                    if isinstance(res, bytes):
                        yield item.decode('iso8859-1')
                    elif hasattr(_vim, 'Dictionary') and isinstance(res, _vim.Dictionary):
                        yield vim._autofixdict(item)
                    elif hasattr(_vim, 'List') and isinstance(res, _vim.List):
                        yield vim._autofixlist(item)
                    else:
                        yield item
                    continue
                return
            def __insert__(self, index, value):
                self.__backing__.insert(index, value)
            def __getitem__(self, index):
                res = self.__backing__[index]
                if isinstance(res, bytes):
                    return res.decode('iso8859-1')
                elif hasattr(_vim, 'Dictionary') and isinstance(res, _vim.Dictionary):
                    return vim._autofixdict(res)
                elif hasattr(_vim, 'List') and isinstance(res, _vim.List):
                    return vim._autofixlist(res)
                return res
            def __setitem__(self, index, value):
                self.__backing__[index] = value
            def __delitem__(self, index):
                del self.__backing__[index]

        class _autofixdict(collections.MutableMapping):
            def __init__(self, backing):
                self.__backing__ = backing
            def __iter__(self):
                for name in self.__backing__.keys():
                    yield name.decode('iso8859-1') if isinstance(name, bytes) else name
                return
            def __len__(self):
                return len(self.__backing__)
            def __getitem__(self, name):
                rname = name.encode('iso8859-1')
                res = self.__backing__[rname]
                if isinstance(res, bytes):
                    return res.decode('iso8859-1')
                elif hasattr(_vim, 'Dictionary') and isinstance(res, _vim.Dictionary):
                    return vim._autofixdict(res)
                elif hasattr(_vim, 'List') and isinstance(res, _vim.List):
                    return vim._autofixlist(res)
                return res
            def __setitem__(self, name, value):
                rname = name.encode('iso8859-1')
                self.__backing__[rname] = value
            def __delitem__(self, name):
                realname = name.encode('iso8859-1')
                del self.__backing__[rname]

        class _accessor(object):
            def __init__(self, result): self.result = result
            def __get__(self, obj, objtype): return self.result
            def __set__(self, obj, val): self.result = val

        class _vars(object):
            def __new__(cls, prefix="", name=None):
                ns = cls.__dict__.copy()
                ns.setdefault('prefix', (prefix + ':') if len(prefix) > 0 else prefix)
                [ ns.pop(item, None) for item in ['__new__', '__dict__', '__weakref__'] ]
                result = type( (prefix + cls.__name__[1:]) if name is None else name, (object,), ns)
                return result()
            def __getitem__(self, name):
                try: return vim.eval(self.prefix + name)
                except: pass
                return None   # FIXME: this right?
            def __setitem__(self, name, value):
                return vim.command("let {:s} = {:s}".format(self.prefix+name, vim._to(value)))

        # converters
        @classmethod
        def _to(cls, n):
            if isinstance(n, integer_types):
                return str(n)
            if isinstance(n, float):
                return "{:f}".format(n)
            if isinstance(n, string_types):
                return "{!r}".format(n)
            if isinstance(n, list):
                return "[{:s}]".format(','.join(map(cls._to, n)))
            if isinstance(n, dict):
                return "{{{:s}}}".format(','.join((':'.join((cls._to(k), cls._to(v))) for k, v in n.items())))
            raise Exception("Unknown type {:s} : {!r}".format(type(n),n))

        @classmethod
        def _from(cls, n):
            if isinstance(n, string_types):
                if n.startswith('['):
                    return cls._from(eval(n))
                if n.startswith('{'):
                    return cls._from(eval(n))
                try: return float(n) if '.' in n else float('.')
                except ValueError: pass
                try: return int(n)
                except ValueError: pass
                return str(n)
            if isinstance(n, list):
                return [ cls._from(item) for item in n ]
            if isinstance(n, dict):
                return { str(k) : cls._from(v) for k, v in n.items() }
            return n

        # error class
        _error = getattr(_vim, 'error', Exception)
        class error(_error if issubclass(_error, Exception) else Exception):
            """An exception originating from vim's python implementation."""

        # buffer/window
        buffers = _accessor(_vim.buffers)
        current = _accessor(_vim.current)

        # vim.command and evaluation (local + remote)
        if (_vim.eval('has("clientserver")')) and False:
            @classmethod
            def command(cls, string, count=16):
                cmd, escape = string.replace("'", "''"), ''
                return _vim.command("call remote_send(v:servername, \"{:s}:\" . '{:s}' . \"\n\")".format(count * escape, cmd))

            @classmethod
            def eval(cls, string):
                cmd = string.replace("'", "''")
                return cls._from(_vim.eval("remote_expr(v:servername, '{:s}')".format(cmd)))

        else:
            @classmethod
            def command(cls, string): return _vim.command(string)
            @classmethod
            def eval(cls, string): return cls._from(_vim.eval(string))

        # global variables
        if hasattr(_vim, 'vars'):
            gvars = _autofixdict(_vim.vars) if hasattr(_vim, 'Dictionary') and isinstance(_vim.vars, _vim.Dictionary) else _vim.vars
        else:
            gvars = _vars('g')

        # misc variables (buffer, window, tab, script, vim)
        bvars, wvars, tvars, svars, vvars = map(_vars, 'bwtsv')

        # dictionary
        if hasattr(_vim, 'Diictionary'):
            @classmethod
            def Dictionary(cls, dict):
                return _vim.Dictionary(dict)
        else:
            @classmethod
            def Dictionary(cls, dict):
                Frender = lambda value: "{!r}".format(value) if isinstance(value, string_types) else "{!s}".format(value)
                rendered = [(Frender(key), Frender(value)) for key, value in dict.items() if isinstance(value, (string_types, integer_types))]
                return cls.eval("{}{:s}{}".format('{', ','.join("{:s}:{:s}".format(*pair) for pair in rendered), '}'))

        # functions
        if hasattr(_vim, 'Function'):
            @classmethod
            def Function(cls, name):
                return _vim.Function(name)
        else:
            @classmethod
            def Function(cls, name):
                def caller(*args):
                    return cls.command("call {:s}({:s})".format(name, ','.join(map(cls._to, args))))
                caller.__name__ = name
                return caller

        class tab(object):
            """Internal vim commands for interacting with tabs"""
            goto = staticmethod(lambda n: vim.command("tabnext {:d}".format(1 + n)))
            close = staticmethod(lambda n: vim.command("tabclose {:d}".format(1 + n)))
            #def move(n, t):    # FIXME
            #    current = int(vim.eval('tabpagenr()'))
            #    _ = t if current == n else current if t > current else current + 1
            #    vim.command("tabnext {:d} | tabmove {:d} | tabnext {:d}".format(1 + n, t, _))

            getCurrent = staticmethod(lambda: int(vim.eval('tabpagenr()')) - 1)
            getCount = staticmethod(lambda: int(vim.eval('tabpagenr("$")')))
            getBuffers = staticmethod(lambda n: [ int(item) for item in vim.eval("tabpagebuflist({:d})".format(n - 1)) ])

            getWindowCurrent = staticmethod(lambda n: int(vim.eval("tabpagewinnr({:d})".format(n - 1))))
            getWindowPrevious = staticmethod(lambda n: int(vim.eval("tabpagewinnr({:d}, '#')".format(n - 1))))
            getWindowCount = staticmethod(lambda n: int(vim.eval("tabpagewinnr({:d}, '$')".format(n - 1))))

        class buffer(object):
            """Internal vim commands for getting information about a buffer"""
            name = staticmethod(lambda id: str(vim.eval("bufname({!s})".format(id))))
            number = staticmethod(lambda id: int(vim.eval("bufnr({!s})".format(id))))
            window = staticmethod(lambda id: int(vim.eval("bufwinnr({!s})".format(id))))
            exists = staticmethod(lambda id: bool(vim.eval("bufexists({!s})".format(id))))
            new = staticmethod(lambda name: buffer.new(name))
            of = staticmethod(lambda id: buffer.of(id))

        class window(object):
            """Internal vim commands for doing things with a window"""

            # ui position conversion
            @staticmethod
            def positionToLocation(position):
                if position in {'left', 'above'}:
                    return 'leftabove'
                if position in {'right', 'below'}:
                    return 'rightbelow'
                raise ValueError(position)

            @staticmethod
            def positionToSplit(position):
                if position in {'left', 'right'}:
                    return 'vsplit'
                if position in {'above', 'below'}:
                    return 'split'
                raise ValueError(position)

            @staticmethod
            def optionsToCommandLine(options):
                result = []
                for k, v in options.items():
                    if isinstance(v, string_types):
                        result.append("{:s}={:s}".format(k, v))
                    elif isinstance(v, bool):
                        result.append("{:s}{:s}".format('' if v else 'no', k))
                    elif isinstance(v, integer_types):
                        result.append("{:s}={:d}".format(k, v))
                    else:
                        raise NotImplementedError(k, v)
                    continue
                return '\\ '.join(result)

            # window selection
            @staticmethod
            def current():
                '''return the current window number'''
                return int(vim.eval('winnr()'))

            @staticmethod
            def select(window):
                '''Select the window with the specified window number'''
                return (int(vim.eval('winnr()')), vim.command("{:d} wincmd w".format(window)))[0]

            @staticmethod
            def currentsize(position):
                if position in ('left', 'right'):
                    return int(vim.eval('&columns'))
                if position in ('above', 'below'):
                    return int(vim.eval('&lines'))
                raise ValueError(position)

            # properties
            @staticmethod
            def buffer(window):
                '''Return the bufferid for the specified window'''
                return int(vim.eval("winbufnr({:d})".format(window)))

            @staticmethod
            def available(bufferid):
                '''Return the first window number for a buffer id'''
                return int(vim.eval("bufwinnr({:d})".format(bufferid)))

            # window actions
            @classmethod
            def create(cls, bufferid, position, ratio, options, preview=False):
                '''create a window for the bufferid and return its number'''
                last = cls.current()

                size = cls.currentsize(position) * ratio
                if preview:
                    if len(options) > 0:
                        vim.command("noautocmd silent {:s} pedit! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), cls.optionsToCommandLine(options), vim.buffer.name(bufferid)))
                    else:
                        vim.command("noautocmd silent {:s} pedit! {:s}".format(cls.positionToLocation(position), vim.buffer.name(bufferid)))
                    vim.command("noautocmd silent! wincmd P")
                else:
                    if len(options) > 0:
                        vim.command("noautocmd silent {:s} {:d}{:s}! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), int(size), cls.positionToSplit(position), cls.optionsToCommandLine(options), vim.buffer.name(bufferid)))
                    else:
                        vim.command("noautocmd silent {:s} {:d}{:s}! {:s}".format(cls.positionToLocation(position), int(size), cls.positionToSplit(position), vim.buffer.name(bufferid)))

                # grab the newly created window
                new = cls.current()
                try:
                    if bool(vim.gvars['incpy#WindowPreview']):
                        return new

                    newbufferid = cls.buffer(new)
                    if bufferid > 0 and newbufferid == bufferid:
                        return new

                    # if the bufferid doesn't exist, then we have to recreate one.
                    if vim.eval("bufnr({:d})".format(bufferid)) < 0:
                        raise Exception("The requested buffer ({:d}) does not exist and will need to be created.".format(bufferid))

                    # if our new bufferid doesn't match the requested one, then we switch to it.
                    elif newbufferid != bufferid:
                        vim.command("buffer {:d}".format(bufferid))
                        logger.debug("Adjusted buffer ({:d}) for window {:d} to point to the correct buffer id ({:d})".format(newbufferid, new, bufferid))

                finally:
                    cls.select(last)
                return new

            @classmethod
            def show(cls, bufferid, position, ratio, options, preview=False):
                '''return the window for the bufferid, recreating it if its now showing'''
                window = cls.available(bufferid)

                # if we already have a windowid for the buffer, then we can return it. otherwise
                # we rec-reate the window which should get the buffer to work.
                return window if window > 0 else cls.create(bufferid, position, ratio, options, preview=preview)

            @classmethod
            def hide(cls, bufferid, preview=False):
                last = cls.select(cls.buffer(bufferid))
                if preview:
                    vim.command("noautocmd silent pclose!")
                else:
                    vim.command("noautocmd silent close!")
                return cls.select(last)

            # window state
            @classmethod
            def saveview(cls, bufferid):
                last = cls.select( cls.buffer(bufferid) )
                res = vim.eval('winsaveview()')
                cls.select(last)
                return res

            @classmethod
            def restview(cls, bufferid, state):
                do = vim.Function('winrestview')
                last = cls.select( cls.buffer(bufferid) )
                do(state)
                cls.select(last)

            @classmethod
            def savesize(cls, bufferid):
                last = cls.select( cls.buffer(bufferid) )
                w, h = map(vim.eval, ['winwidth(0)', 'winheight(0)'])
                cls.select(last)
                return { 'width':w, 'height':h }

            @classmethod
            def restsize(cls, bufferid, state):
                window = cls.buffer(bufferid)
                return "vertical {:d} resize {:d} | {:d} resize {:d}".format(window, state['width'], window, state['height'])

# fd-like wrapper around vim buffer object
class buffer(object):
    """vim buffer management"""

    # Scope of the buffer instance
    def __init__(self, buffer):
        if type(buffer) != type(vim.current.buffer):
            raise AssertionError
        self.buffer = buffer
        #self.writing = threading.Lock()

    def close(cls):
        # if vim is going down, then it will crash trying to do anything
        # with python...so if it is, don't try to clean up.
        if vim.vvars['dying']:
            return
        vim.command("silent! bdelete! {:d}".format(self.buffer.number))

    # Creating a buffer from various inputs
    @classmethod
    def new(cls, name):
        """Create a new incpy.buffer object named `name`."""
        vim.command("silent! badd {:s}".format(name))

        # Now that the buffer has been added, we can try and fetch it by name
        return cls.of(name)

    @classmethod
    def exists(cls, identity):
        '''Return a boolean on whether a buffer of the specified `identity` exists.'''

        # If we got a vim.buffer, then it exists because the user
        # has given us a reference ot it.
        if isinstance(identity, _vim.Buffer):
            return True

        # Create some closures that we can use to verify the buffer
        # matches what the user asked for.
        def match_name(buffer):
            return buffer.name is not None and buffer.name.endswith(identity)
        def match_id(buffer):
            return buffer.number == identity

        # Figure out which closure we need to use based on the parameter type
        if isinstance(identity, string_types):
            res, match = "'{:s}'".format(identity.replace("'", "''")), match_name

        elif isinstance(identity, integer_types):
            res, match = "{:d}".format(identity), match_id

        else:
            raise vim.error("Unable to identify buffer due to invalid parameter type : {!s}".format(identity))

        # Now we just need to ask vim if the buffer exists and return it
        return bool(vim.eval("bufexists({!s})".format(res)))

    @classmethod
    def of(cls, identity):
        """Return an incpy.buffer object with the specified `identity` which can be either a name or id number."""

        # If we were already given a vim.buffer instance, then there's
        # really nothing for us to actually do.
        if isinstance(identity, _vim.Buffer):
            return cls(identity)

        # Create some matcher callables that we can search with
        def match_name(buffer):
            return buffer.name is not None and buffer.name.endswith(identity)
        def match_id(buffer):
            return buffer.number == identity

        # Figure out which matcher type we need to use based on the type
        if isinstance(identity, string_types):
            res, match = "'{:s}'".format(identity.replace("'", "''")), match_name

        elif isinstance(identity, integer_types):
            res, match = "{:d}".format(identity), match_id

        else:
            raise vim.error("Unable to determine buffer from parameter type : {!s}".format(identity))

        # If we iterated through everything, then we didn't find a match
        if not vim.eval("bufexists({!s})".format(res)):
            raise vim.error("Unable to find buffer from parameter : {!s}".format(identity))

        # Iterate through all our buffers finding the first one that matches
        try:
            # FIXME: It sucks that this is O(n), but what else can we do?
            buf = next(buffer for buffer in vim.buffers if match(buffer))

        # If we iterated through everything, then we didn't find a match
        except StopIteration:
            raise vim.error("Unable to find buffer from parameter : {!s}".format(identity))

        # Now we can construct our class using the buffer we found
        else:
            return cls(buf)

    # Properties
    name = property(fget=lambda self: self.buffer.name)
    number = property(fget=lambda self: self.buffer.number)

    def __repr__(self):
        cls = self.__class__
        return "<{:s} {:d} \"{:s}\">".format('.'.join([__name__, cls.__name__]), self.number, self.name)

    # Editing buffer the buffer in-place
    def write(self, data):
        result = iter(data.split('\n'))
        self.buffer[-1] += next(result)
        [ self.buffer.append(item) for item in result ]

    def clear(self):
        self.buffer[:] = ['']

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

    def __init__(self, bufnum, opt, preview, tab=None):
        """Create a view for the specified buffer.

        Buffer can be an existing buffer, an id number, filename, or even a new name.
        """
        self.options = opt
        self.preview = preview

        # Get the vim.buffer from the buffer the caller gave us.
        try:
            buf = vim.buffer.of(bufnum)

        # If we couldn't find the desired buffer, then we'll just create one
        # with the name that we were given.
        except Exception as E:

            # Create a buffer with the specified name. This is not really needed
            # as we're only creating it to sneak off with the buffer's name.
            if isinstance(bufnum, string_types):
                buf = vim.buffer.new(bufnum)
            elif isinstance(bufnum, integer_types):
                buf = vim.buffer.new(vim.gvars['incpy#WindowName'])
            else:
                raise vim.error("Unable to determine output buffer name from parameter : {!r}".format(bufnum))

        # Now we can grab the buffer's name so that we can use it to re-create
        # the buffer if it was deleted by the user.
        self.__buffer_name = buf.number
        #res = "'{!s}'".format(buf.name.replace("'", "''"))
        #self.__buffer_name = vim.eval("fnamemodify({:s}, \":.\")".format(res))

    @property
    def buffer(self):
        name = self.__buffer_name

        # Find the buffer by the name that was previously cached.
        try:
            result = vim.buffer.of(name)

        # If we got an exception when trying to snag the buffer by its name, then
        # log the exception and create a new one to take the old one's place.
        except vim.error as E:
            logger.info("recreating output buffer due to exception : {!s}".format(E), exc_info=True)

            # Create a new buffer using the name that we expect it to have.
            if isinstance(name, string_types):
                result = vim.buffer.new(name)
            elif isinstance(name, integer_types):
                result = vim.buffer.new(vim.gvars['incpy#WindowName'])
            else:
                raise vim.error("Unable to determine output buffer name from parameter : {!r}".format(name))

        # Return the buffer we found back to the caller.
        return result
    @buffer.setter
    def buffer(self, number):
        id = vim.eval("bufnr({:d})".format(number))
        name = vim.eval("bufname({:d})".format(id))
        if id < 0:
            raise vim.error("Unable to locate buffer id from parameter : {!r}".format(number))
        elif not name:
            raise vim.error("Unable to determine output buffer name from parameter : {!r}".format(number))
        self.__buffer_name = id

    @property
    def window(self):
        result = self.buffer
        return vim.window.buffer(result.number)

    def write(self, data):
        """Write data directly into window contents (updating buffer)"""
        result = self.buffer
        return result.write(data)

    # Methods wrapping the window visibility and its scope
    def create(self, position, ratio):
        """Create window for buffer"""
        bufobj = self.buffer

        # FIXME: creating a view in another tab is not supported yet
        if vim.buffer.number(bufobj.number) == -1:
            raise Exception("Buffer {:d} does not exist".format(bufobj.number))
        if 1.0 <= ratio < 0.0:
            raise Exception("Specified ratio is out of bounds {!r}".format(ratio))

        # create the window, get its buffer, and update our state with it.
        window = vim.window.create(bufobj.number, position, ratio, self.options, preview=self.preview)
        self.buffer = vim.eval("winbufnr({:d})".format(window))
        return window

    def show(self, position, ratio):
        """Show window at the specified position if it is not already showing."""
        bufobj = self.buffer

        # FIXME: showing a view in another tab is not supported yet
        # if buffer does not exist then recreate the fucker
        if vim.buffer.number(bufobj.number) == -1:
            raise Exception("Buffer {:d} does not exist".format(bufobj.number))
        # if vim.buffer.window(bufobj.number) != -1:
        #    raise Exception("Window for {:d} is already showing".format(bufobj.number))

        window = vim.window.show(bufobj.number, position, ratio, self.options, preview=self.preview)
        self.buffer = vim.eval("winbufnr({:d})".format(window))
        return window

    def hide(self):
        """Hide the window"""
        bufobj = self.buffer

        # FIXME: hiding a view in another tab is not supported yet
        if vim.buffer.number(bufobj.number) == -1:
            raise Exception("Buffer {:d} does not exist".format(bufobj.number))
        if vim.buffer.window(bufobj.number) == -1:
            raise Exception("Window for {:d} is already hidden".format(bufobj.number))

        return vim.window.hide(bufobj.number, preview=self.preview)

    def __repr__(self):
        cls, name = self.__class__, self.buffer.name
        descr = "{:d}".format(name) if isinstance(name, integer_types) else "\"{:s}\"".format(name)
        identity = descr if buffer.exists(self.__buffer_name) else "(missing) {:s}".format(descr)
        if self.preview:
            return "<{:s} buffer:{:d} {:s} preview>".format('.'.join([__name__, cls.__name__]), self.window, identity)
        return "<{:s} buffer:{:d} {:s}>".format('.'.join([__name__, cls.__name__]), self.window, identity)
