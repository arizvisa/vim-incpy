import sys, functools, codecs, operator, itertools, contextlib
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
        if _vim.eval('has("clientserver")') and not 'enabled':

            # FIXME: this is currently disabled because it exposes a race condition
            #        when sending a command that adds a buffer. the issue is that when
            #        using `remote_send(..., ":badd buf\n")`, the command will succeed,
            #        but the `vim.buffers` list hasn't yet been updated. another symptom
            #        is that using `remote_send(..., ":!ls\n") directly after the "badd"
            #        will list the added buffer, but using `:ls!` (without a "remote_send")
            #        will show that the buffer does not exist.

            @classmethod
            def command(cls, string):
                cmd, escape, exitmode = string.replace("'", "''"), '', ''
                remote = "call remote_send(v:servername, \"{:s}\" . ':' . '{:s}' . \"{:s}\")".format(exitmode, cmd, r'\n')
                return _vim.command(remote)

            @classmethod
            def eval(cls, string):
                cmd = string.replace("'", "''")
                remote = "remote_expr(v:servername, '{:s}')".format(cmd)
                serialized = _vim.eval(remote)
                if '\n' in serialized:
                    iterable = (cls._from(line) for line in serialized.split('\n') if line)
                    return [item for item in iterable]
                return cls._from(serialized)

        else:
            @classmethod
            def command(cls, string): return _vim.command(string)
            @classmethod
            def eval(cls, string): return cls._from(_vim.eval(string))

        @classmethod
        def has(cls, feature):
            '''Return whether the editor supports the requested feature.'''
            return cls.eval("has('{:s}')".format(feature.replace("'", "''")))

        # global variables
        if hasattr(_vim, 'vars'):
            gvars = _autofixdict(_vim.vars) if hasattr(_vim, 'Dictionary') and isinstance(_vim.vars, _vim.Dictionary) else _vim.vars
        else:
            gvars = _vars('g')

        # misc variables (buffer, window, tab, script, vim)
        bvars, wvars, tvars, svars, vvars = map(_vars, 'bwtsv')

        # dictionary
        if hasattr(_vim, 'Dictionary'):
            @classmethod
            def Dictionary(cls, dict):
                return _vim.Dictionary(dict)
        else:
            @classmethod
            def Dictionary(cls, dict):
                Frender = lambda value: "{!r}".format(value) if isinstance(value, string_types) else "{!s}".format(value)
                rendered = [(Frender(key), Frender(value)) for key, value in dict.items() if isinstance(value, (string_types, integer_types))]
                return cls.eval("{}{:s}{}".format('{', ','.join("{:s}:{:s}".format(*pair) for pair in rendered), '}'))

        # buffers
        Buffer = _accessor(_vim.Buffer if hasattr(_vim, 'Buffer') else _vim.current.buffer.__class__)

        # functions
        if hasattr(_vim, 'Function'):
            @classmethod
            def Function(cls, name):
                '''Return a callable that executes the specified vim function.'''
                return _vim.Function(name)

            @classmethod
            def FunctionWithResult(cls, name):
                '''Return a callable that executes the specified vim function and returns its result.'''
                return _vim.Function(name)
        else:
            @classmethod
            def Function(cls, name):
                '''Return a callable that executes the specified vim function.'''
                def caller(*args):
                    return cls.command("call {:s}({:s})".format(name, ','.join(map(cls._to, args))))
                caller.__name__ = name
                return caller

            @classmethod
            def FunctionWithResult(cls, name):
                '''Return a callable that executes the specified vim function and returns its result.'''
                def caller(*args):
                    return cls.eval("{:s}({:s})".format(name, ','.join(map(cls._to, args))))
                caller.__name__ = name
                return caller

        class buffer(object):
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
                if isinstance(identity, vim.Buffer):
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

            @classmethod
            @contextlib.contextmanager
            def update(cls, identity):
                '''Return a context manager that can be used to modify the specified buffer.'''
                number = cls.of(identity)
                buffer = cls.by(number)
                needs_preservation = 'modifiable' in buffer.options
                modifiable = buffer.options['modifiable'] if needs_preservation else True
                try:
                    if needs_preservation and not modifiable:
                        buffer.options['modifiable'] = True
                    yield buffer

                finally:
                    if needs_preservation:
                        buffer.options['modifiable'] = modifiable
                    pass
                return

        class window(object):
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

        class tab(object):
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

        class terminal(object):
            """Internal vim commands for interacting with terminal jobs by their buffer number"""
            exists = staticmethod(lambda buffer: len(vim.eval("term_getsize({:d})".format(buffer))) > 0)

            @classmethod
            def start(cls, cmd, **options):
                '''Start the specified command as a terminal job and return the buffer number.'''
                return vim.FunctionWithResult('term_start')(cmd, vim.Dictionary(options))

            @classmethod
            def stop(cls, buffer):
                '''Stop the terminal job running in the specified buffer.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to stop the job in buffer {:d} as it is not associated with a job.".format(buffer))
                return vim.eval("job_stop(term_getjob({:d}))".format(buffer))

            @classmethod
            def info(cls, buffer):
                '''Return information for the terminal job in the specified buffer as a dictionary.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to get information for job in buffer {:d} as it is not associated with a job.".format(buffer))
                return vim.eval("job_info(term_getjob({:d}))".format(buffer))

            @classmethod
            def status(cls, buffer):
                '''Return the status for the terminal job in the specified buffer as a string.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to get the status for job in buffer {:d} as it is not associated with a job.".format(buffer))
                return vim.eval("term_getstatus({:d})".format(buffer))

            @classmethod
            def send(cls, buffer, keys):
                '''Send the given keystrokes to the terminal job in the specified buffer.'''
                return vim.FunctionWithResult('term_sendkeys')(buffer, keys)

            @classmethod
            def wait(cls, buffer, *timeout):
                '''Wait for any pending updates to the terminal job in the specified buffer.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to wait on the terminal job in buffer {:d} as it is not associated with a job.".format(buffer))
                return vim.Function('term_wait')(buffer, *timeout)

        class neoterminal(object):
            """Internal neovim commands for interacting with terminal jobs by their buffer number"""
            exists = staticmethod(lambda buffer: len(vim.eval("jobwait([{:d}], 0) != -3".format(buffer))) > 0)

            # fortunately the &channel option seems to be immutable, so
            # we can just query it from the buffer variables to extract it.
            job = staticmethod(lambda buffer: vim.eval("getbufvar({:d}, '&channel')".format(buffer)))

            @classmethod
            def start(cls, cmd, **options):
                '''Start the specified command as a terminal job and return the buffer number.'''
                cwd = vim.eval("fnamemodify({:s}, ':~')".format('getcwd()'))
                job = vim.eval("termopen({!r}, {!s})".format(cmd, options))

                # XXX: we should be able to determine the buffer name from the `cwd`, `pid`, and
                #      `cmd`, but (for some reason) "termopen" starts up multiple instances of the
                #      neovim python provider when there are no writable buffers available for
                #      replacement...or at least when neovim starts up..anyways.
                #
                #      somehow the aforementioned condition results in the wrong job id being
                #      returned by our call to "termopen()". it is wrong in that it doesn't
                #      correlate with the id from the "b:terminal_job_id" buffer variable. so,
                #      when we use said job id to get the pid via "jobpid()", we get a completely
                #      wrong process id. thus our entire predicted buffer name will be wrong.

                #pid = vim.eval("jobpid({:d})".format(job))
                #name = "term://{cwd}//{pid}:{command}".format(cwd=cwd, pid=pid, command=cmd)
                #assert(vim.eval("bufexists('{:s}')".format(name.replace("'", "''"))))
                #return vim.eval("bufnr('{:s}')".format(name.replace("'", "''")))

                # we have no choice but to iterate through all of the buffers while
                # trying to find the one where the '&channel' number matches our job.
                infos = [info for info in vim.eval('getbufinfo()')]
                filtered = [info for info in infos if 'terminal_job_id' in info.get('variables', {})]
                matching = [info for info in filtered if info['variables']['terminal_job_id'] == job]

                # now we just need to filter our matching results and return the buffer from them.
                results = {info['bufnr'] for info in matching}
                if len(results) != 1:
                    raise vim.error("Unable to locate the buffer that is associated with job {:d}{:s}.".format(job, " ({:s})".format(', '.join(map("{:d}".format, results))) if results else ''))
                elif not vim.eval("bufexists({:d})".format(*results)):
                    raise vim.error("An error with the identified buffer ({:d}) for job {:d} has occurred as the buffer does not exist.".format(int(*results), job))
                return int(*results)

            @classmethod
            def stop(cls, buffer):
                '''Stop the terminal job running in the specified buffer.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to stop the job in buffer {:d} as it is not associated with a job.".format(buffer))
                job = cls.job(buffer)
                return vim.eval("jobstop({:d})".format(job))

            @classmethod
            def info(cls, buffer):
                '''Return information for the terminal job in the specified buffer as a dictionary.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to get information for job in buffer {:d} as it is not associated with a job.".format(buffer))
                job = cls.job(buffer)
                pid = vim.eval("jobpid({:d})".format(job))
                return {'process': pid}

            @classmethod
            def status(cls, buffer):
                '''Return the status for the terminal job in the specified buffer as a string.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to get the status for job in buffer {:d} as it is not associated with a job.".format(buffer))
                job = cls.job(buffer)
                res = vim.eval("jobwait([{:d}], 0)".format(job))
                if res == -1:
                    return 'running'
                return 'finished'

            @classmethod
            def send(cls, buffer, keys):
                '''Send the given keystrokes to the terminal job in the specified buffer.'''
                job = cls.job(buffer)

                # neovim doesn't like us using newlines, so we need to give it
                # a list if we want to send any keypresses that include them.
                return vim.eval("chansend({:d}, {!r})".format(job, keys.split('\n')))

            @classmethod
            def wait(cls, buffer, *timeout):
                '''Wait for any pending updates to the terminal job in the specified buffer.'''
                if not cls.exists(buffer):
                    raise vim.error("Unable to wait on the terminal job in buffer {:d} as it is not associated with a job.".format(buffer))

                # there's no need to wait for things in neovim. apparently they
                # assume that the buffer (window) will always be up-to-date. we
                # still honor the sleep timeout, though, if we received one.
                timeout and vim.eval("wait({:f}, {:s})".format(max(0, *timeout), 'v:false'))

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

class buffer(object):
    """vim buffer management"""

    @classmethod
    def new(cls, name_or_number_or_buffer):
        if isinstance(name_or_number_or_buffer, type(vim.current.buffer)):
            return cls(name_or_number_or_buffer.number)
        elif isinstance(name_or_number_or_buffer, string_types):
            return cls(vim.buffer.new(name_or_number_or_buffer))
        elif not vim.buffer.exists(name_or_number_or_buffer):
            raise vim.error("Unable to find buffer from parameter : {!s}".format(name_or_number_or_buffer))
        return cls(name_or_number_or_buffer)

    # Scope
    def __init__(self, number):
        self.buffer = vim.buffers[number]

    def close(self):
        res = self.buffer.number
        return vim.buffer.close(res)

    def __repr__(self):
        cls = self.__class__
        return "<{:s} {:d} lines:{:d} \"{:s}\">".format('.'.join([__name__, cls.__name__]), self.buffer.number, len(self.buffer), self.buffer.name)

    # Properties
    name = property(fget=lambda self: self.buffer.name)
    number = property(fget=lambda self: self.buffer.number)
    exists = property(fget=lambda self: vim.buffer.exists(self.buffer.number))

    # Things that make this look like a file.
    def __get_buffer_index(self):
        position = 0
        for item in self.buffer:
            yield position, item
            position += len(item)
        return

    def write(self, data):
        lines = iter(data.split('\n'))
        with vim.buffer.update(self.buffer) as buffer:
            buffer[-1] += next(lines)
            [ buffer.append(item) for item in lines ]
        return

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
        self.__buffer__ = res = buffer.new(bufferobj)
        self.windows = vim.buffer.windows(res.number)

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
        count = vim.tab.count()
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
        last, mutable_options = vim.window.current(), options.copy()

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
        new = vim.window.current()
        try:
            newnumber = vim.window.buffer(new)

            # if the buffer id for the new window matches the one
            # that we've cached, then we can return the window id.
            if number > 0 and newnumber == number:
                return new

            # if the buffer number doesn't exist, then we have to recreate one.
            if not vim.buffer.exists(number):
                raise Exception("The requested buffer ({:d}) does not exist and will need to be created.".format(number))

            # if our new buffer number doesn't match the requested one, then we switch to it.
            elif newnumber != number:
                vim.command("buffer {:d}".format(number))
                logger.debug("Adjusted buffer ({:d}) for window {:d} to point to the correct buffer id ({:d})".format(newnumber, new, number))

        # select the previous window that we saved.
        finally:
            vim.window.select(last)
        return new

    def add(self, tab, position, size, **options):
        tabnumber = 0 if tab == vim.tab.current() else tab
        window = self.__create_window(self.buffer.number, position, size, options, tab=tabnumber)
        self.windows.add(window)
        return window

    def hide(self, window):
        last, number = vim.window.current(), self.buffer.number

        # first check the window type so that we can figure
        # out which command we'll need to use to close it.
        preview = vim.window.type(window) == 'preview'
        if not preview and not vim.window.exists(window):
            return self.windows.discard(window) or -1

        # figure out whether the window that we're hiding
        # is in the same tab or found in a different one.
        wtab, wnumber = vim.window.tab_and_number(window)
        tabnumber = 0 if wtab == vim.tab.current() else wtab
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
            vim.window.select(last)
        return window

    def show(self, tab, position, size, **options):
        number = self.buffer.number
        tab = tab or vim.tab.current()

        # check if the current tab has a window open to our buffer.
        # if it doesn't, then we'll need to add a window one for it.
        available = vim.tab.buffers(tab)
        if number not in available:
            return self.add(tab, position, size, **options)

        # otherwise, we need to figure out the window id.
        tabwindows = vim.tab.windows(tab)
        windows = vim.buffer.windows(number)
        iterable = (window for window in tabwindows & windows)

        # we need to figure out the best window id, so we'll need to sort the windows
        # we received. we do this using the area of the window and its width or height.
        Fkey_window_area = lambda window: (lambda width, height: width * height)(*vim.window.dimensions(window))
        Fkey_window_width = lambda window: (lambda width, height: (width * height, width))(*vim.window.dimensions(window))
        Fkey_window_height = lambda window: (lambda width, height: (width * height, height))(*vim.window.dimensions(window))
        Fkey_window = Fkey_window_width if position in {'above', 'below'} else Fkey_window_height if position in {'left', 'right'} else Fkey_window_area

        # Now we can sort our resulting windows and grab the largest one.
        ordered = sorted(iterable, key=Fkey_window)
        if ordered:
            iterable = reversed(ordered)
            focused = next(iterable)
            len(ordered) > 1 and logger.debug("Returning the currently showing window ({:d}) with the largest dimensions ({:s}) from the others ({:s}).".format(focused, "{:d}x{:d}".format(*vim.window.dimensions(focused)), ', '.join(map("{:d}".format, sorted(iterable)))))
            return focused

        # Otherwise, we can just ignore trying to figure out which window
        # we own. Returning the window id is just a formality anyways.
        logger.debug("Unable to determine ownership of the currently showing windows ({:s}).".format(', '.join(map("{:d}".format, sorted(windows)))))
        return -1

    def close(self):
        last, number = vim.window.current(), self.buffer.number
        tab, windows = vim.tab.current(), vim.buffer.windows(number)

        # Convert the window ids to a snapshot of each id keyed by the tab and window number.
        window_locations = {window: vim.window.tab_and_number(window) for window in windows}

        # Now we'll extract the tab number into a list, and remove the
        # current tab from it so that we can close those windows last.
        tabs = {}
        for window, (wtab, wnumber) in window_locations.items():
            tabs.setdefault(wtab, []).append(window)
        tabs = {wtab : {window for window in windows} for wtab, windows in tabs.items()}

        # Next we'll need to use our current tab to remove
        # the associated windows from our tab dictionary.
        current, others, available = {tab: tabs.pop(tab)}, tabs, windows

        # Now we'll build the command that we'll execute in each tab
        # that we'll use to close all windows that opened our buffer.
        tabpage_comparison = "tabpagenr() != {:d}".format(*current)
        buffer_comparison = "bufnr() == {:d}".format(number)
        preview_check_command = "win_gettype(winnr()) == \"{:s}\"".format('preview')
        prefix_command = 'noautocmd silent'
        close_window_command = "execute printf(\"{:s} %sclose!\", ({:s})? \"{:s}\" : \"{:s}\")".format(prefix_command, preview_check_command, 'p', '')

        # Finally we can traverse through all of the other tabs and close all windows
        # associated with our buffer. We repeat the process for the current tab too.
        conditional = "if {:s} | {:s} | endif".format(buffer_comparison, close_window_command)
        do_window_command = "windo {:s}".format(conditional)
        [ vim.command("{:d}tabdo {:s}".format(otab, do_window_command)) for otab in sorted(others)[::-1] ]
        [ vim.command(do_window_command) for otab in current ]

        # That should've closed absolutely everything. For sanity, though we
        # go ahead and verify that we've closed all references to the buffer.
        everything = itertools.chain(others.items(), current.items())
        iterable = itertools.chain(*(windows for _, windows in everything))
        known, closed = self.windows, {window for window in iterable}

        unmanaged = closed - known
        unmanaged_description = map("{:d}".format, unmanaged)
        logger.debug("Closed {:d} windows associated with buffer ({:d}) of which {:d} window{:s} were not managed by us ({:s}).".format(len(closed), number, len(unmanaged), '' if len(unmanaged) == 1 else 's', ','.join(unmanaged_description)))

        # If there are still any windows open, then bail and raise an exception.
        remaining = vim.buffer.windows(number)
        if len(remaining) > 0:
            raise vim.error("Unable to close {:d} window{:s} ({:s}) associated with buffer ({:d}).".format(len(remaining), '' if len(remaining) == 1 else 's', ','.join(map("{:d}".format, remaining)), number))

        # Now that we know that there's no windows open to our buffer,
        # we can close the buffer and be done with this class forever.
        try:
            self.buffer.close()
        finally:
            buffer, self.__buffer__ = self.__buffer__, None
            vim.window.select(last) if vim.window.exists(last) else last
        return

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
        tab, format = vim.window.tab(window), "P{:d}".format if vim.window.type(window) == 'preview' else "{:d}".format
        return '#'.join(["{:d}".format(tab), format(window)])

    def __repr__(self):
        cls, name, number = self.__class__, self.buffer.name, self.buffer.number
        description = "{:d}".format(name) if isinstance(name, integer_types) else "\"{:s}\"".format(name)
        buffer_description = description if vim.buffer.exists(number) else "(missing) {:s}".format(description)
        window_descriptions = map(self.__repr_describe_window, vim.buffer.windows(number))
        return "<{:s} buffer:{:s} windows:({:s})>".format('.'.join([__name__, cls.__name__]), buffer_description, ','.join(window_descriptions))
