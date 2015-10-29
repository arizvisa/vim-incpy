try:
    import vim as _vim,exceptions

    # vim wrapper
    class vim(object):
        class _accessor(object):
            def __init__(self, result): self.result = result
            def __get__(self, obj, objtype): return self.result
            def __set__(self, obj, val): self.result = val

        class _vars(object):
            def __new__(cls, prefix="", name=None):
                ns = dict(cls.__dict__)
                ns.setdefault('prefix', (prefix+':') if len(prefix)> 0 else prefix)
                map(lambda n,d=ns: d.pop(n,None), ('__new__','__dict__','__weakref__'))
                result = type( (prefix+cls.__name__[1:]) if name is None else name, (object,), ns)
                return result()
            def __getitem__(self, name):
                try: return vim.eval(self.prefix + name)
                except: pass
                return None   # FIXME: this right?
            def __setitem__(self, name, value):
                return vim.command('let %s = %s'% (self.prefix+name, vim._to(value)))

        # converters
        @classmethod
        def _to(cls, n):
            if type(n) in (int,long):
                return str(n)
            if type(n) is float:
                return '%f'% n
            if type(n) is str:
                return repr(n)
            if type(n) is list:
                return '[%s]'% ','.join(map(cls._to,n))
            if type(n) is dict:
                return '{%s}'% ','.join((':'.join((cls._to(k),cls._to(v))) for k,v in n.iteritems()))
            raise Exception, "Unknown type %s : %r"%(type(n),n)

        @classmethod
        def _from(cls, n):
            if type(n) is str:
                if n.startswith('['):
                    return cls._from(eval(n))
                if n.startswith('{'):
                    return cls._from(eval(n))
                try: return float(n) if '.' in n else float('.')
                except ValueError: pass
                try: return int(n)
                except ValueError: pass
                return str(n)
            if type(n) is list:
                return map(cls._from, n)
            if type(n) is dict:
                return dict((str(k),cls._from(v)) for k,v in n.iteritems())
            return n

        # error class
        _error = _vim.error
        class error(exceptions.Exception):
            """because vim is using old-style exceptions based on str"""

        # buffer/window
        buffers = _accessor(_vim.buffers)
        current = _accessor(_vim.current)

        # vim.command and evaluation (local + remote)
        if (_vim.eval('has("clientserver")')) and False:
            @classmethod
            def command(cls, string):
                cmd,escape = string.replace('"', r'\"'), ''*16
                return _vim.command('call remote_send(v:servername, "%s:%s\n")'% (escape,cmd))

            @classmethod
            def eval(cls, string):
                cmd = string.replace('"', r'\"')
                return cls._from(_vim.eval('remote_expr(v:servername, "%s")'% cmd))

        else:
            @classmethod
            def command(cls, string): return _vim.command(string)
            @classmethod
            def eval(cls, string): return cls._from(_vim.eval(string))

        # global variables
        gvars = _accessor(_vim.vars) if hasattr(_vim, 'vars') else _vars('g')

        # misc variables (buffer, window, tab, script, vim)
        bvars,wvars,tvars,svars,vvars = map(_vars, 'bwtsv')

        # functions
        if hasattr(_vim, 'Function'):
            @classmethod
            def Function(cls, name):
                return _vim.Function(name)
        else:
            @classmethod
            def Function(cls, name):
                def caller(*args):
                    return cls.command("call %s(%s)"%(name,','.join(map(cls._to,args))))
                caller.__name__ = name
                return caller

    # fd-like wrapper around vim buffer object
    class buffer(object):
        """vim buffer management"""
        ## instance scope
        def __init__(self, buffer):
            assert type(buffer) == type(vim.current.buffer)
            self.buffer = buffer
            #self.writing = threading.Lock()
        def __del__(self):
            self.__destroy(self.buffer)

        # creating a buffer from various input
        @classmethod
        def new(cls, name):
            """Create a new incpy.buffer object named /name/"""
            buf = cls.__create(name)
            return cls(buf)
        @classmethod
        def from_id(cls, id):
            """Return an incpy.buffer object from a buffer id"""
            buf = cls.search_id(id)
            return cls(buf)
        @classmethod
        def from_name(cls, name):
            """Return an incpy.buffer object from a buffer name"""
            buf = cls.search_name(name)
            return cls(buf)

        # properties
        name = property(fget=lambda s:s.buffer.name)
        number = property(fget=lambda s:s.buffer.number)

        def __repr__(self):
            return '<incpy.buffer %d "%s">'%( self.number, self.name )

        ## class methods for helping with vim buffer scope
        @classmethod
        def __create(cls, name):
            vim.command(r'silent! badd %s'% (name,))
            return cls.search_name(name)
        @classmethod
        def __destroy(cls, buffer):
            # if vim is going down, then it will crash trying to do anything
            # with python...so if it is, don't try to clean up.
            if vim.vvars['dying']: return
            vim.command(r'silent! bdelete! %d'% buffer.number)

        ## searching buffers
        @staticmethod
        def search_name(name):
            for b in vim.buffers:
                if b.name is not None and b.name.endswith(name):
                    return b
                continue
            raise vim.error("unable to find buffer '%s'"% name)
        @staticmethod
        def search_id(number):
            for b in vim.buffers:
                if b.number == number:
                    return b
                continue
            raise vim.error("unable to find buffer %d"% number)

        ## editing buffer
        def write(self, data):
            result = iter(data.split('\n'))
            self.buffer[-1] += result.next()
            map(self.buffer.append, result)

        def clear(self): self.buffer[:] = ['']

except ImportError:
    #import logging
    #logging.warn("%s:unable to import vim module. leaving wrappers undefined.", __name__)
    pass

import sys,os,threading,weakref,subprocess,time,itertools

# monitoring an external process' i/o via threads/queues
class process(object):
    """Spawns a program along with a few monitoring threads for allowing asynchronous(heh) interaction with a subprocess.

    mutable properties:
    program -- subprocess.Popen instance
    commandline -- subprocess.Popen commandline
    eventWorking -- threading.Event() instance for signalling task status to monitor threads
    stdout,stderr -- callables that are used to process available work in the taskQueue

    properties:
    id -- subprocess pid
    running -- returns true if process is running and monitor threads are workingj
    working -- returns true if monitor threads are working
    threads -- list of threads that are monitoring subprocess pipes
    taskQueue -- Queue.Queue() instance that contains work to be processed
    exceptionQueue -- Queue.Queue() instance containing exceptions generated during processing
    (process.stdout, process.stderr)<Queue> -- Queues containing output from the spawned process.
    """

    program = None              # subprocess.Popen object
    id = property(fget=lambda s: s.program and s.program.pid or -1)
    running = property(fget=lambda s: False if s.program is None else s.program.poll() is None)
    working = property(fget=lambda s: s.running and not s.eventWorking.is_set())
    threads = property(fget=lambda s: list(s.__threads))

    taskQueue = property(fget=lambda s: s.__taskQueue)
    exceptionQueue = property(fget=lambda s: s.__exceptionQueue)

    def __init__(self, command, **kwds):
        """Creates a new instance that monitors subprocess.Popen(/command/), the created process starts in a paused state.

        Keyword options:
        env<dict> = os.environ -- environment to execute program with
        cwd<str> = os.getcwd() -- directory to execute program  in
        shell<bool> = True -- whether to treat program as an argument to a shell, or a path to an executable
        newlines<bool> = True -- allow python to tamper with i/o to convert newlines
        show<bool> = False -- if within a windowed environment, open up a console for the process.
        paused<bool> = False -- if enabled, then don't start the process until .start() is called
        timeout<float> = -1 -- if positive, then raise a Queue.Empty exception at the specified interval.
        """
        # default properties
        self.__threads = weakref.WeakSet()
        self.__kwds = kwds
        self.commandline = command

        import Queue
        self.eventWorking = threading.Event()
        self.__taskQueue = Queue.Queue()
        self.__exceptionQueue = Queue.Queue()

        self.stdout = kwds.pop('stdout')
        self.stderr = kwds.pop('stderr')

        # start the process
        not kwds.get('paused',False) and self.start(command)

    def start(self, command=None, **options):
        """Start the specified ``command`` with the requested **options"""
        kwds = dict(self.__kwds)
        kwds.update(options)
        command = command or self.commandline

        env = kwds.get('env', os.environ)
        cwd = kwds.get('cwd', os.getcwd())
        newlines = kwds.get('newlines', True)
        shell = kwds.get('shell', False)
        stdout,stderr = options.pop('stdout',self.stdout),options.pop('stderr',self.stderr)
        self.program = process.subprocess(command, cwd, env, newlines, joined=(stderr is None) or stdout == stderr, shell=shell, show=kwds.get('show', False))
        self.commandline = command

        # monitor program's i/o
        self.__start_monitoring(stdout, stderr)
        self.__start_updater(timeout=kwds.get('timeout',-1))

        # start monitoring
        self.eventWorking.set()
        return self

    def __start_updater(self, daemon=True, timeout=0):
        """Start the updater thread. **used internally**"""
        import Queue
        def task_exec(emit, data):
            if hasattr(emit,'send'):
                res = emit.send(data)
                res and P.write(res)
            else: emit(data)

        def task_get_timeout(P, timeout):
            try:
                emit,data = P.taskQueue.get(block=True, timeout=timeout)
            except Queue.Empty:
                _,_,tb = sys.exc_info()
                P.exceptionQueue.put(StopIteration,StopIteration(),tb)
                return ()
            return emit,data

        def task_get_notimeout(P, timeout):
            return P.taskQueue.get(block=True)

        task_get = task_get_timeout if timeout > 0 else task_get_notimeout

        def update(P, timeout):
            import Queue
            P.eventWorking.wait()
            while P.eventWorking.is_set():
                res = task_get(P, timeout)
                if not res: continue
                emit,data = res

                try:
                    task_exec(emit,data)
                except StopIteration:
                    P.eventWorking.clear()
                except:
                    P.exceptionQueue.put(sys.exc_info())
                finally:
                    P.taskQueue.task_done()
                continue
            return

        self.updater = updater = threading.Thread(target=update, name="thread-%x.update"% self.id, args=(self,timeout))
        updater.daemon = daemon
        updater.start()
        return updater

    def __start_monitoring(self, stdout, stderr=None):
        """Start monitoring threads. **used internally**"""
        program = self.program
        name = 'thread-{:x}'.format(program.pid)

        # create monitoring threads + coroutines
        if stderr:
            res = process.monitorPipe(self.taskQueue, (stdout,program.stdout),(stderr,program.stderr), name=name)
        else:
            res = process.monitorPipe(self.taskQueue, (stdout,program.stdout), name=name)

        res = map(None,res)
        # attach a method for injecting data into a monitor
        for t,q in res: t.send = q.send
        threads,senders = zip(*res)

        # update threads for destruction later
        self.__threads.update(threads)

        # set things off
        for t in threads: t.start()

    @staticmethod
    def subprocess(program, cwd, environment, newlines, joined, shell=True, show=False):
        """Create a subprocess using subprocess.Popen."""
        stderr = subprocess.STDOUT if joined else subprocess.PIPE
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags = subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0 if show else subprocess.SW_HIDE
            cf = subprocess.CREATE_NEW_CONSOLE if show else 0
            return subprocess.Popen(program, universal_newlines=newlines, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, close_fds=False, startupinfo=si, creationflags=cf, cwd=cwd, env=environment)
        return subprocess.Popen(program, universal_newlines=newlines, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, close_fds=True, cwd=cwd, env=environment)

    @staticmethod
    def monitorPipe(q, (id,pipe), *more, **options):
        """Attach a coroutine to a monitoring thread for stuffing queue `q` with data read from `pipe`

        Yields a list of (thread,coro) tuples given the arguments provided.
        Each thread will read from `pipe`, and stuff the value combined with `id` into `q`.
        """
        def stuff(q,*key):
            while True: q.put(key+((yield),))

        for id,pipe in itertools.chain([(id,pipe)],more):
            res,name = stuff(q,id), '{:s}<{!r}>'.format(options.get('name',''),id)
            yield process.monitor(res.next() or res.send, pipe, name=name),res
        return

    @staticmethod
    def monitor(send, pipe, blocksize=1, daemon=True, name=None):
        """Spawn a thread that reads `blocksize` bytes from `pipe` and dispatches it to `send`

        For every single byte, `send` is called. The thread is named according to
        the `name` parameter.

        Returns the monitoring threading.thread instance 
        """
        def shuffle(send, pipe):
            while not pipe.closed:
                data = pipe.read(blocksize)
                if len(data) == 0:
                    # pipe.read syscall was interrupted. so since we can't really
                    # determine why (cause...y'know..python), stop dancing so
                    # the parent will actually be able to terminate us
                    break
                map(send,data)
            return
        if name:
            monitorThread = threading.Thread(target=shuffle, name=name, args=(send,pipe))
        else:
            monitorThread = threading.Thread(target=shuffle, args=(send,pipe))
        monitorThread.daemon = daemon
        return monitorThread

    def write(self, data):
        """Write `data` directly to program's stdin"""
        if self.program is not None and self.program.poll() is None and not self.program.stdin.closed:
            return self.program.stdin.write(data)

        pid,result = self.program.pid,self.program.poll()
        raise IOError, 'Unable to write to stdin for process %d. Process %s'% (pid, 'is still running.' if result is None else 'has terminated with code %d.'% result)

    def close(self):
        """Closes stdin of the program"""
        if self.program is not None and self.program.poll() is None and not self.program.stdin.closed:
            return self.program.stdin.close()

        pid,result = self.program.pid,self.program.poll()
        raise IOError, 'Unable to close stdin for process %d. Process %s'% (pid, 'is still running.' if result is None else 'has terminated with code %d.'% result)

    def signal(self, signal):
        """Raise a signal to the program"""
        if self.program is not None and self.program.poll() is None:
            return self.program.send_signal(signal)

        pid,result = self.program.pid,self.program.poll()
        raise IOError, 'Unable to raise signal %r in process %d. Process %s'% (signal, pid, 'is still running.' if result is None else 'has terminated with code %d.'% result)

    def throw(self):
        """Grab an exception if there's any available"""
        res = self.exceptionQueue.get()
        self.exceptionQueue.task_done()
        return res

    def wait(self, timeout=0.0):
        """Wait a given amount of time for the process to terminate"""
        program = self.program
        if program is None:
            raise RuntimeError, 'Program %s is not running'% self.commandline

        if not self.running: return program.returncode
        self.eventWorking.wait()

        if timeout:
            t = time.time()
            while self.running and self.eventWorking.is_set() and time.time() - t < timeout:        # spin cpu until we timeout
                if not self.exceptionQueue.empty():
                    res = self.throw()
                    raise res[0],res[1],res[2]
                continue
            if not self.eventWorking.is_set():
                return self.__terminate()
            return program.returncode

        # return program.wait() # XXX: doesn't work correctly with PIPEs due to
        #   pythonic programmers' inability to understand os semantics

        while self.running and self.eventWorking.is_set():
            if not self.exceptionQueue.empty():
                res = self.throw()
                raise res[0],res[1],res[2]
            continue    # ugh...poll-forever/kill-cpu until program terminates...
        if not self.eventWorking.is_set():
            return self.__terminate()
        return program.returncode

    def stop(self):
        self.eventWorking.clear()
        return self.__terminate()

    def __terminate(self):
        """Sends a SIGKILL signal and then waits for program to complete"""
        self.program.kill()
        while self.running:
            if not self.exceptionQueue.empty():
                res = self.throw()
                raise res[0],res[1],res[2]
            continue
        self.__stop_monitoring()
        return self.program.returncode

    def __stop_monitoring(self):
        """Cleanup monitoring threads"""
        P = self.program
        if P.poll() is None:
            raise RuntimeError, "Unable to stop monitoring while process {!r} is still running.".format(P)

        # stop the update thread
        self.eventWorking.clear()

        # forcefully close pipes that still open, this should terminate the monitor threads
        #   also, this fixes a resource leak since python doesn't do this on subprocess death
        for p in (P.stdin,P.stdout,P.stderr):
            while p and not p.closed:
                try: p.close()
                except: pass

        def forever(iterable):
            while len(iterable) > 0:
                for n in list(iterable):
                    yield n
                    del(n)
            return

        # join all monitoring threads, and spin until none of them are alive
        [ x.join() for x in self.__threads]
        for th in forever(self.__threads):
            if not th.is_alive():
                self.__threads.discard(th)
            continue

        # join the updater thread, and then remove it
        self.updater.join()
        assert not self.updater.is_alive()
        self.updater = None
        return

    def __repr__(self):
        if self.running:
            return '<process running pid:%d>'%( self.id )
        return '<process not-running cmd:"%s">'%( self.commandline )

## interface for wrapping the process class
def spawn(stdout, command, **options):
    """Spawn `command` with the specified `**options`.

    If program writes anything to stdout, dispatch it to the `stdout` callable.
    If `stderr` is defined, call `stderr` with anything written to the program's stderr.
    """
    # grab arguments that we care about
    stderr = options.pop('stderr', None)
    daemon = options.pop('daemon', True)

    # empty out the first generator result if a coroutine is passed
    if hasattr(stdout,'send'):
        res = stdout.next()
        res and P.write(res)
    if hasattr(stderr,'send'):
        res = stderr.next()
        res and P.write(res)

    # spawn the sub-process
    return process(command, stdout=stdout, stderr=stderr, **options)

