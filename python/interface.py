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
