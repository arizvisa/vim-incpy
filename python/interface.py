import sys, functools, codecs, operator, itertools
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
            def __init__(self, *result, **callables):
                if result:
                    self._slot = []
                    self._get = (lambda slot: lambda: slot[0])(self._slot)
                    self._set = (lambda slot: lambda value: [slot.clear(), slot.append(value)])(self._slot)
                    self._slot.append(*result)
                else:
                    self._get, self._set = callables.get('get'), callables.get('set')
                return
            def __get__(self, obj, objtype=None):
                if callable(self._get):
                    return self._get()
                raise AttributeError('unreadable attribute')
            def __set__(self, obj, val):
                if callable(self._set):
                    return self._set(val)
                raise AttributeError('can\'t set attribute')

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
        tabpages = _accessor(_vim.tabpages)

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

            # utilities for finding a window using its buffer id
            window_id = staticmethod(lambda bufnum: int(vim.eval("bufwinid({:d})".format(bufnum))))
            window_ids = staticmethod(lambda bufnum: [wid for wid in map(int, vim.eval("win_findbuf({:d})".format(bufnum)))])
            windows = classmethod(lambda bufnum: [int(vim.eval("win_id2win({:d})".format(wid))) for wid in cls.window_ids(bufnum)])

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

            @classmethod
            def type(cls, window):
                res = vim.eval("win_gettype({:d})".format(window))
                return None if res == 'unknown' else res

            @staticmethod
            def available(bufferid):
                '''Return the first window number for a buffer id'''
                return int(vim.eval("bufwinnr({:d})".format(bufferid)))

            # window actions
            @classmethod
            def create(cls, bufferid, position, ratio, options):
                '''create a window for the bufferid and return its number'''
                last, mutable_options = cls.current(), options.copy()

                preview = mutable_options.pop('preview', False)
                size = cls.currentsize(position) * ratio
                if preview:
                    if len(mutable_options) > 0:
                        vim.command("noautocmd silent {:s} pedit! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), cls.optionsToCommandLine(mutable_options), vim.buffer.name(bufferid)))
                    else:
                        vim.command("noautocmd silent {:s} pedit! {:s}".format(cls.positionToLocation(position), vim.buffer.name(bufferid)))
                    vim.command("noautocmd silent! wincmd P")
                else:
                    if len(mutable_options) > 0:
                        vim.command("noautocmd silent {:s} {:d}{:s}! +setlocal\\ {:s} {:s}".format(cls.positionToLocation(position), int(size), cls.positionToSplit(position), cls.optionsToCommandLine(mutable_options), vim.buffer.name(bufferid)))
                    else:
                        vim.command("noautocmd silent {:s} {:d}{:s}! {:s}".format(cls.positionToLocation(position), int(size), cls.positionToSplit(position), vim.buffer.name(bufferid)))

                # grab the newly created window
                new = cls.current()
                try:
                    if preview:
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
            def show(cls, bufferid, position, ratio, options):
                '''return the window for the bufferid, recreating it if its now showing'''
                window = cls.available(bufferid)

                # if we already have a windowid for the buffer, then we can return it. otherwise
                # we rec-reate the window which should get the buffer to work.
                return window if window > 0 else cls.create(bufferid, position, ratio, options)

            @classmethod
            def hide(cls, bufferid):
                last = cls.select(cls.buffer(bufferid))
                res = vim.window.type(vim.buffer.window(bufferid))

                # If it's a "preview" window, then use the right command to close it.
                if res == 'preview':
                    vim.command("noautocmd silent pclose!")

                # Otherwise, treat it like a normal window to close.
                elif res:
                    vim.command("noautocmd silent close!")

                # FIXME: should probably raise an exception or log something
                #        if we can't find the window that needs to be closed.
                else:
                    pass
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

        class newbuffer(object):
            """Internal vim commands for getting information about a buffer"""
            name = staticmethod(lambda number: str(vim.eval("bufname({!s})".format(number))))
            exists = staticmethod(lambda number: bool(vim.eval("bufexists({!s})".format(number))))
            count = staticmethod(lambda *attribute: sum(1 for info in filter(operator.itemgetter(*attribute) if attribute else None, vim.eval('getbufinfo()'))))
            available = staticmethod(lambda *attribute: {info['bufnr'] for info in filter(operator.itemgetter(*attribute) if attribute else None, vim.eval('getbufinfo()'))})

            # utilities for finding a window using its buffer id
            @classmethod
            def windows(cls, number):
                '''Return the list of window ids for the specified buffer number.'''
                res = vim.eval("getbufinfo({:d})".format(number))
                iterable = itertools.chain(*(info['windows'] for info in res))
                return {id for id in map(int, iterable)}

            # managing the scope of a buffer
            @classmethod
            def new(cls, name):
                '''Add a new buffer with the specified name and return its buffer number.'''
                vim.command("silent! badd {:s}".format(name))
                return cls.of(name)

            @classmethod
            def close(cls, number):
                '''Delete and unload the specified buffer from the buffer list.'''
                # if vim is going down, then it will crash trying to do anything
                # with python...so, don't even attempt to delete the buffer.
                if vim.vvars['dying']:
                    return
                vim.command("silent! bdelete! {:d}".format(number))

            @classmethod
            def by(cls, number):
                '''Return the `vim.Buffer` object for the specified buffer number.'''
                iterable = (buffer for buffer in vim.buffers)
                filtered = (buffer for buffer in iterable if buffer.number == number)
                result = next(filtered, None)
                if result is None:
                    raise vim.error("Unable to find buffer from number ({!s})".format(number))
                return result

            @classmethod
            def of(cls, identity):
                '''Return the buffer number for the specified name, number, or buffer.'''
                if isinstance(identity, _vim.Buffer):
                    return identity.number

                # Grab the info using identity as a buffer number.
                elif isinstance(identity, integer_types):
                    infos = vim.eval("getbufinfo({:d})".format(identity))

                # Grab the info using identity as a buffer name.
                elif isinstance(identity, string_types):
                    escaped = identity.replace("'", "''")
                    infos = vim.eval("getbufinfo('{:s}')".format(escaped))

                # We don't support any other types...
                else:
                    raise vim.error("Unable to determine buffer from parameter type : {!s}".format(identity))

                # Extract our results from the buffer info that we queried.
                results = {int(info['bufnr']) for info in infos}
                if len(results) != 1:
                    raise vim.error("Unable to find buffer from parameter : {!s}".format(identity))
                [number] = results

                # Verify that the buffer actually exists before returning it.
                if not cls.exists(number):
                    raise vim.error("Unable to find buffer from parameter : {!s}".format(identity))
                return number

        class newwindow(object):
            exists = staticmethod(lambda window: -1 < int(vim.eval("winbufnr({!s})".format(window))))

            @classmethod
            def number(cls, windowid):
                '''Return the window number for the window with the specified id.'''
                res = vim.eval("win_id2win({:d})".format(windowid))
                return int(res)

            @classmethod
            def count(cls, *tab):
                '''Return the number of windows for the specified tab or all available tabs.'''
                iterable = (selected or int(vim.eval('tabpagenr()')) for selected in tab)
                formatted = (integer for integer in map("{:d}".format, iterable))
                tabinfo = vim.eval("gettabinfo({:s})".format(next(formatted, '')), *formatted)
                iterable = (info['windows'] for info in tabinfo)
                return sum(map(len, iterable))

            @classmethod
            def buffer(cls, windowid):
                '''Return the buffer number for the window with the specified id.'''
                iterable = (info for info in vim.eval("getwininfo({:d})".format(windowid)))
                numbers = {int(info['bufnr']) for info in iterable}
                if len(numbers) != 1:
                    raise vim.error("Unable to get the buffer number for the specified id ({:d})".format(windowid))
                [number] = numbers
                return number

            @classmethod
            def tab_and_number(cls, windowid):
                '''Return the tab and window number for the window with the specified id.'''
                [tab, number] = map(int, vim.eval("win_id2tabwin({:d})".format(windowid)))
                return tab, number

            @classmethod
            def tab(cls, windowid):
                '''Return the tab number for the window with the specified id.'''
                tab, _ = cls.tab_and_number(windowid)
                return tab

            @classmethod
            def select(cls, windowid):
                '''Select the window with the specified window id.'''
                ok = int(vim.eval("win_gotoid({:d})".format(windowid)))
                return True if ok else False

            @classmethod
            def current(cls):
                '''Return the window id for the current window.'''
                res = vim.eval('win_getid(winnr(), tabpagenr())')
                return int(res)

            @classmethod
            def type(cls, windowid):
                '''Return the type for the window with the specified id as a string.'''
                res = vim.eval("win_gettype({:d})".format(windowid))
                return None if res == 'unknown' else res

            @classmethod
            def dimensions(cls, windowid):
                '''Return the dimensions for the window with the specified id.'''
                iterable = (info for info in vim.eval("getwininfo({:d})".format(windowid)))
                dimensions = {(int(info['width']), int(info['height'])) for info in iterable}
                if len(dimensions) != 1:
                    raise vim.error("Unable to get window information for the specified id ({:d})".format(windowid))
                [dimension] = dimensions
                return dimension

        class newtab(object):
            """Internal vim commands for interacting with tabs"""
            @classmethod
            def current(cls):
                '''Return the current tab page number.'''
                return int(vim.eval('tabpagenr()'))

            @classmethod
            def count(cls):
                '''Return the current number of tabs.'''
                return int(vim.eval("tabpagenr('{:s}')".format('$')))

            @classmethod
            def buffers(cls, tab):
                '''Return a list of the buffer numbers for the specified tab.'''
                iterable = vim.eval("tabpagebuflist({:s})".format("{:d}".format(tab) if tab else '')) or []
                return {int(number) for number in iterable}

            @classmethod
            def windows(cls, *tab):
                '''Return a list of the window ids for the specified tab.'''
                iterable = (info for info in vim.eval("gettabinfo({:s})".format("{:d}".format(*tab) if tab else '')))
                filtered = (info for info in iterable if operator.eq(int(info['tabnr']), *tab))
                identifiers = itertools.chain(*(info['windows'] for info in filtered))
                return {int(windowid) for windowid in identifiers}

        dimensions = _accessor(get=lambda: tuple(int(vim.eval('&' + option)) for option in ['columns', 'lines']))
        width = _accessor(get=lambda: int(vim.eval('&columns')))
        height = _accessor(get=lambda: int(vim.eval('&lines')))
        available_buffers = _accessor(get=lambda: {int(info['bufnr']) for info in vim.eval('getbufinfo()')})
        available_windows = _accessor(get=lambda: {int(info['winid']) for info in vim.eval('getwininfo()')})

        @classmethod
        def size(cls, position):
            '''Return the dimensions of the user interface for the editor.'''
            columns, lines = cls.dimensions
            if position in {'left', 'right'}:
                return columns
            if position in {'above', 'below'}:
                return lines
            raise ValueError(position)

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

class newbuffer(object):
    """vim buffer management"""

    @classmethod
    def new(cls, name_or_number_or_buffer):
        if isinstance(name_or_number_or_buffer, type(vim.current.buffer)):
            return cls(name_or_number_or_buffer.number)
        elif isinstance(name_or_number_or_buffer, string_types):
            return cls(vim.newbuffer.new(name_or_number_or_buffer))
        elif not vim.newbuffer.exists(name_or_number_or_buffer):
            raise vim.error("Unable to find buffer from parameter : {!s}".format(name_or_number_or_buffer))
        return cls(name_or_number_or_buffer)

    # Scope
    def __init__(self, number):
        self.buffer = vim.buffers[number]

    def close(self):
        res = self.buffer.number
        return vim.newbuffer.close(res)

    def __repr__(self):
        cls = self.__class__
        return "<{:s} {:d} lines:{:d} \"{:s}\">".format('.'.join([__name__, cls.__name__]), self.buffer.number, len(self.buffer), self.buffer.name)

    # Properties
    name = property(fget=lambda self: self.buffer.name)
    number = property(fget=lambda self: self.buffer.number)
    exists = property(fget=lambda self: vim.newbuffer.exists(self.buffer.number))

    # Things that make this look like a file.
    def __get_buffer_index(self):
        position = 0
        for item in self.buffer:
            yield position, item
            position += len(item)
        return

    def write(self, data):
        lines = iter(data.split('\n'))
        self.buffer[-1] += next(lines)
        [ self.buffer.append(item) for item in lines ]

    def writable(self):
        return False

    def truncate(self, pos=None):
        if pos is None:
            self.buffer[:] = ['']
        else:
            iterable = ((index, item) for index, item in self.__get_buffer_index())
            iterable, complete = itertools.tee(iterable)
            count = sum(1 for item in itertools.takewhile(functools.partial(operator.gt, pos), map(operator.itemgetter(0), iterable)))
            sliced = [item for item in itertools.islice(complete, count)]
            index, last = sliced[-1] if sliced else (0, '')
            trimmed = itertools.chain(map(operator.itemgetter(1), sliced[:-1]), [last[:pos - index]])
            self.buffer[:] = [item for item in trimmed]
        return

    # These exist, but aren't really intended to be implemented. The requirements
    # for implementing these consists of tracking and updating an index that
    # can be used for converting a character position to the buffer line number.
    def read(self, amount=-1):
        raise NotImplementedError('read', amount)

    def readable(self):
        return False

    def seek(self, target, whence=0):
        raise NotImplementedError('seek', target, whence)

    def seekable(self):
        return False

class multiview(object):
    """This manages the windows associated with a buffer."""

    # Create a fake descriptor that always returns the default encoding.
    class encoding_descriptor(object):
        def __init__(self):
            self.module = __import__('sys')
        def __get__(self, obj, type=None):
            return self.module.getdefaultencoding()
    encoding = encoding_descriptor()
    del(encoding_descriptor)

    def __init__(self, bufferobj):
        self.__buffer__ = buffer = newbuffer.new(bufferobj)
        self.windows = vim.newbuffer.windows(buffer.number)

    @property
    def buffer(self):
        if self.__buffer__ is not None:
            return self.__buffer__
        raise vim.error('Unable to access buffer for managing windows due to the buffer having been closed.')

    @classmethod
    def __create_window_options(cls, options):
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

    @classmethod
    def __create_window_split_keyword(cls, position):
        if position in {'left', 'right'}:
            return 'vsplit'
        elif position in {'above', 'below'}:
            return 'split'
        raise ValueError(position)

    @classmethod
    def __create_window_location_keyword(cls, position):
        if position in {'left', 'above'}:
            return 'leftabove'
        elif position in {'right', 'below'}:
            return 'rightbelow'
        raise ValueError(position)

    @classmethod
    def __create_window_tab_keyword(cls, tab):
        count = vim.newtab.count()
        if isinstance(tab, string_types) and any([tab.startswith('new'), not(tab)]):
            return "{:s}tab".format(tab[3:] or '$') if tab else ''
        elif not isinstance(tab, integer_types):
            raise vim.error("Unable to determine tab location from parameter : {!s}".format(tab))
        elif tab > count:
            return "{:s}tab".format('$')
        return "{:d}tabdo".format(tab) if tab else ''

    @classmethod
    def __create_window(cls, number, position, size, options, tab=0):
        '''create a window for the buffer number and return its window id'''
        last, mutable_options = vim.newwindow.current(), options.copy()

        location = cls.__create_window_location_keyword(position)
        split_type = cls.__create_window_split_keyword(position)
        tabdo = cls.__create_window_tab_keyword(tab)
        location_prefix = ' '.join([tabdo, location]) if tabdo else location

        preview = mutable_options.pop('preview', False)
        option_keywords = cls.__create_window_options(mutable_options)
        option_set_command = "setlocal\\ {:s}".format(option_keywords) if len(mutable_options) > 0 else ''

        if preview:
            setlocal_command = "+{:s} ".format(option_set_command) if option_set_command else ''
            vim.command("noautocmd silent {:s} pedit! {:s}{:s}".format(location_prefix, setlocal_command, "#{:d}".format(number)))
            vim.command("noautocmd silent! {:s}wincmd P".format("{:s} ".format(tabdo) if tabdo else ''))
        elif split_type:
            setlocal_command = "+{:s} ".format(option_set_command) if option_set_command else ''
            vim.command("noautocmd silent {:s} {:d}{:s}! {:s}{:s}".format(location_prefix, int(size), split_type, setlocal_command, "#{:d}".format(number)))
        else:
            setlocal_command = "+{:s} ".format(option_set_command) if option_set_command else ''
            vim.command("noautocmd silent {:s} edit! {:s}{:s}".format(location_prefix, int(size), setlocal_command, "#{:d}".format(number)))

        # grab the newly created window
        new = vim.newwindow.current()
        try:
            newnumber = vim.newwindow.buffer(new)

            # if the buffer id for the new window matches the one
            # that we've cached, then we can return the window id.
            if number > 0 and newnumber == number:
                return new

            # if the buffer number doesn't exist, then we have to recreate one.
            if not vim.newbuffer.exists(number):
                raise Exception("The requested buffer ({:d}) does not exist and will need to be created.".format(number))

            # if our new buffer number doesn't match the requested one, then we switch to it.
            elif newnumber != number:
                vim.command("buffer {:d}".format(number))
                logger.debug("Adjusted buffer ({:d}) for window {:d} to point to the correct buffer id ({:d})".format(newnumber, new, number))

        # select the previous window that we saved.
        finally:
            vim.newwindow.select(last)
        return new

    def add(self, tab, position, size, **options):
        tabnumber = 0 if tab == vim.newtab.current() else tab
        window = self.__create_window(self.buffer.number, position, size, options, tab=tabnumber)
        self.windows.add(window)
        return window

    def hide(self, window):
        last, number = vim.newwindow.current(), self.buffer.number

        # first check the window type so that we can figure
        # out which command we'll need to use to close it.
        preview = vim.newwindow.type(window) == 'preview'
        if not preview and not vim.newwindow.exists(window):
            return self.windows.discard(window) or -1

        # figure out whether the window that we're hiding
        # is in the same tab or found in a different one.
        wtab, wnumber = vim.newwindow.tab_and_number(window)
        tabnumber = 0 if wtab == vim.newtab.current() else wtab
        tabdo = "{:d}tabdo".format(wtab) if tabnumber else ''
        windo = "{:d}windo".format(wnumber)
        location_prefix = ' '.join([tabdo, windo]) if tabdo else windo

        # now we need to navigate to the target window so that
        # we can close it regardless of the tab it resides in.
        try:
            close_command = "{:s}{:s}".format("{:s} ".format(location_prefix) if location_prefix else '', "{:s}close!".format('p' if preview else ''))
            vim.command("noautocmd silent {:s}".format(close_command))

            # if the window id isn't in our set, then log a warning that
            # we've hidden a window that belongs to the user, not us.
            window not in self.windows and logger.debug("Closed an unmanaged window ({:d}) in tab ({:d}) with number ({:d}).".format(window, wtab, wnumber))
            self.windows.discard(window)

        # afterwards, jump back to the previous window that was in focus. we
        # can discard the error code because if the previous window was the
        # same as what was closed, then we'll go to the alt window anyways.
        finally:
            vim.newwindow.select(last)
        return window

    def show(self, tab, position, size, **options):
        number = self.buffer.number
        tab = tab or vim.newtab.current()

        # check if the current tab has a window open to our buffer.
        # if it doesn't, then we'll need to add a window one for it.
        available = vim.newtab.buffers(tab)
        if number not in available:
            return self.add(tab, position, size, **options)

        # otherwise, we need to figure out the window id.
        tabwindows = vim.newtab.windows(tab)
        windows = vim.newbuffer.windows(number)
        iterable = (window for window in tabwindows & windows)

        # we need to figure out the best window id, so we'll need to sort the windows
        # we received. we do this using the area of the window and its width or height.
        Fkey_window_area = lambda window: (lambda width, height: width * height)(*vim.newwindow.dimensions(window))
        Fkey_window_width = lambda window: (lambda width, height: (width * height, width))(*vim.newwindow.dimensions(window))
        Fkey_window_height = lambda window: (lambda width, height: (width * height, height))(*vim.newwindow.dimensions(window))
        Fkey_window = Fkey_window_width if position in {'above', 'below'} else Fkey_window_height if position in {'left', 'right'} else Fkey_window_area

        # Now we can sort our resulting windows and grab the largest one.
        ordered = sorted(iterable, key=Fkey_window)
        if ordered:
            iterable = reversed(ordered)
            focused = next(iterable)
            len(ordered) > 1 and logger.debug("Returning the currently showing window ({:d}) with the largest dimensions ({:s}) from the others ({:s}).".format(focused, "{:d}x{:d}".format(*vim.newwindow.dimensions(focused)), ', '.join(map("{:d}".format, sorted(iterable)))))
            return focused

        # Otherwise, we can just ignore trying to figure out which window
        # we own. Returning the window id is just a formality anyways.
        logger.debug("Unable to determine ownership of the currently showing windows ({:s}).".format(', '.join(map("{:d}".format, sorted(windows)))))
        return -1

    # forward everything that makes this look like a file to the buffer.
    write = property(fget=lambda self: self.buffer.write)
    writable = property(fget=lambda self: self.buffer.writable)
    read = property(fget=lambda self: self.buffer.read)
    readable = property(fget=lambda self: self.buffer.readable)
    seek = property(fget=lambda self: self.buffer.seek)
    seekable = property(fget=lambda self: self.buffer.seekable)
    truncate = property(fget=lambda self: self.buffer.truncate)

    # hidden methods
    @classmethod
    def __repr_describe_window(cls, window):
        tab, format = vim.newwindow.tab(window), "P{:d}".format if vim.newwindow.type(window) == 'preview' else "{:d}".format
        return '#'.join(["{:d}".format(tab), format(window)])

    def __repr__(self):
        cls, name, number = self.__class__, self.buffer.name, self.buffer.number
        description = "{:d}".format(name) if isinstance(name, integer_types) else "\"{:s}\"".format(name)
        buffer_description = description if vim.newbuffer.exists(number) else "(missing) {:s}".format(description)
        window_descriptions = map(self.__repr_describe_window, vim.newbuffer.windows(number))
        return "<{:s} buffer:{:s} windows:({:s})>".format('.'.join([__name__, cls.__name__]), buffer_description, ','.join(window_descriptions))

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
        self.options['preview'] = preview

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
        window = vim.window.create(bufobj.number, position, ratio, self.options)
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

        window = vim.window.show(bufobj.number, position, ratio, self.options)
        self.buffer = vim.window.buffer(window)
        return window

    def hide(self):
        """Hide the window"""
        bufobj = self.buffer

        # FIXME: hiding a view in another tab is not supported yet
        if vim.buffer.number(bufobj.number) == -1:
            raise Exception("Buffer {:d} does not exist".format(bufobj.number))
        if vim.buffer.window(bufobj.number) == -1:
            raise Exception("Window for {:d} is already hidden".format(bufobj.number))

        return vim.window.hide(bufobj.number)

    def __repr__(self):
        cls, name = self.__class__, self.buffer.name
        descr = "{:d}".format(name) if isinstance(name, integer_types) else "\"{:s}\"".format(name)
        identity = descr if buffer.exists(self.__buffer_name) else "(missing) {:s}".format(descr)
        window_type = vim.window.type(self.window)
        return "<{:s} buffer:{:d} {:s}{:s}>".format('.'.join([__name__, cls.__name__]), self.window, identity, " {:s}".format(window_type) if window_type else '')
