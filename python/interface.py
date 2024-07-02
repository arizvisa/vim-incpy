import six, sys, logging, functools, codecs
logger = logging.getLogger('incpy').getChild('py')

integer_types = tuple({type(sys.maxsize + n) for n in range(2)})
string_types = tuple({type(s) for s in ['', u'']})
text_types = tuple({t.__base__ for t in string_types}) if sys.version_info.major < 3 else string_types
ordinal_types = (string_types, bytes)

try:
    import vim as _vim

    # Try python2's exceptions module first
    try:
        import exceptions

    # Otherwise we're using Python3 and it's a builtin
    except ImportError:
        import builtins as exceptions

    # vim wrapper
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
        _error = getattr(_vim, 'error', exceptions.Exception)
        class error(_error if issubclass(_error, exceptions.Exception) else exceptions.Exception):
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
            return "<incpy.buffer {:d} \"{:s}\">".format(self.number, self.name)

        # Editing buffer the buffer in-place
        def write(self, data):
            result = iter(data.split('\n'))
            self.buffer[-1] += next(result)
            [ self.buffer.append(item) for item in result ]

        def clear(self):
            self.buffer[:] = ['']

except ImportError:
    logger.warning('unable to import the vim module for python-vim. skipping the definition of its wrappers.')

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
