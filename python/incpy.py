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

    Properties:
    (process.stdout, process.stderr)<Queue> -- Queues containing output from the spawned process.
    id<pid_t> -- The pid of the spawned process
    running<bool> -- The current running state of the process
    """

    program = None              # subprocess.Popen object
    stdout,stderr = None,None   # queues containing stdout and stderr
    id = property(fget=lambda s: s.program.pid)
    running = property(fget=lambda s: False if s.program is None else s.program.poll() is None)
    threads = property(fget=lambda s: list(s.__threads))

    #Queue = __import__('multiprocessing').Queue
    Queue = __import__('Queue').Queue       # Queue.Queue allows us to grab a mutex to prevent another thread from interacting w/ it

    def __init__(self, command, **kwds):
        """Creates a new instance that monitors subprocess.Popen(/command/), the created process starts in a paused state.

        Keyword options:
        env<dict> = os.environ -- environment to execute program with
        cwd<str> = os.getcwd() -- directory to execute program  in
        joined<bool> = True -- if disabled, use separate monitoring pipes/threads for both stdout and stderr.
        shell<bool> = True -- whether to treat program as an argument to a shell, or a path to an executable
        newlines<bool> = True -- allow python to tamper with i/o to convert newlines
        hidden<bool> = True -- if within a windowed environment, open up a console for the process.
        """
        # default properties
        self.__threads = weakref.WeakSet()
        self.__kwds = kwds
        self.commandline = command

        # start the process
        self.start(command)

    def start(self, command=None):
        command,kwds = command or self.commandline,self.__kwds

        env = kwds.get('env', os.environ)
        cwd = kwds.get('cwd', os.getcwd())
        joined = kwds.get('joined', True)
        newlines = kwds.get('newlines', True)
        shell = kwds.get('shell', False)
        self.program = process.subprocess(command, cwd, env, newlines, joined=joined, shell=shell, show=kwds.get('hidden', False))
        self.commandline = command

        # monitor program's i/o
        self.start_monitoring(joined)

    def start_monitoring(self, joined=True, **kwds):
        program = self.program

        ## monitor threads (which aren't important if python didn't suck with both threads and gc)
        name = 'thread-%x'% program.pid
        if joined:
            res = process.monitor((name+'.stdout',program.stdout), **kwds)
        else:
            res = process.monitor((name+'.stdout',program.stdout),(name+'.stderr',program.stderr), **kwds)

        # assign the queue to the thread for ease-of-access
        for t,q in res: t.queue = q
        threads,queues = zip(*res)

        # assign queues containing stdout and stderr
        self.__threads.update(threads)
        self.stdout,self.stderr = (q for q,_ in map(None, queues, range(2)))

        # set things off
        for t in threads:
            t.start()
        return 

    @staticmethod
    def subprocess(program, cwd, environment, newlines, joined, shell=True, show=False):
        """Create a subprocess using subprocess.Popen"""
        stderr = subprocess.STDOUT if joined else subprocess.PIPE
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags = subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0 if show else subprocess.SW_HIDE
            cf = subprocess.CREATE_NEW_CONSOLE if show else 0
            return subprocess.Popen(program, universal_newlines=newlines, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, close_fds=False, startupinfo=si, creationflags=cf, cwd=cwd, env=environment)
        return subprocess.Popen(program, universal_newlines=newlines, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, close_fds=True, cwd=cwd, env=environment)

    @staticmethod
    def monitor((name,pipe), *more, **kwds):
        """Create multiple monitoring threads for a number of pipes

        Returns a list of (thread,queue) tuples given the number of tuples provided as an argument.
        This creates a list of threads responsible for reading from /pipe/ and storing it into an asynchronous queue
        """
        return [ process.monitorPipe(name,pipe, **kwds) for name,pipe in [(name,pipe)]+list(more) ]
    
    @staticmethod
    def monitorPipe(id, pipe, blocksize=1, daemon=True):
        """Create a monitoring thread that stuffs data from a pipe into a queue.

        Returns a (threading.Thread, Queue)
        (Queues are the only python object that allow you to timeout if data isn't currently available)
        """

        def shuffle(queue, pipe):
            while not pipe.closed:
                data = pipe.read(blocksize)
                if len(data) == 0:
                    # pipe.read syscall was interrupted. so since we can't really
                    # determine why (cause...y'know..python), stop dancing so
                    # the parent will actually be able to terminate us
                    break
                queue.put(data)
            return

        q = process.Queue()
        if id is None:
            monitorThread = threading.Thread(target=shuffle, args=(q,pipe))
        else:
            monitorThread = threading.Thread(target=shuffle, name=id, args=(q,pipe))
        monitorThread.daemon = daemon
        return monitorThread,q

    def write(self, data):
        """Write data directly to program's stdin"""
        if self.running:
            return self.program.stdin.write(data)

        pid,result = self.program.pid,self.program.poll()
        raise IOError, 'Unable to write to terminated process %d. Process terminated with a returncode of %d'% (pid,result)

    def signal(self, signal):
        """Raise a signal to the program"""
        if self.running:
            return self.program.send_signal(signal)

        pid,result = self.program.pid,self.program.poll()
        raise IOError, 'Unable to signal terminated process %d. Process terminated with a returncode of %d'% (pid,result)

    def wait(self, timeout=0.0):
        """Wait a given amount of time for the process to terminate"""
        program = self.program

        if timeout:
            t = time.time()
            while t + timeout > time.time():        # spin cpu until we timeout
                if program.poll() is not None:
                    return program.returncode
                continue
            return None

        # return program.wait() # XXX: doesn't work correctly with PIPEs due to
        #   pythonic programmers' inability to understand os semantics

        while program.poll() is not None:
            pass    # ugh...poll-forever/kill-cpu until program terminates...
        return program.returncode

    def stop(self):
        """Sends a SIGKILL signal and then waits for program to complete"""
        if not self.running:
            self.stop_monitoring()
            return self.program.poll()

        p,_ = self.program,self.program.kill()
        while p.poll() is not None: pass
        self.stop_monitoring()
        self.program = None
        return p.returncode

    def stop_monitoring(self):
        """Cleanup monitoring threads"""

        # close pipes that have been left open since python fails to do this on program death
        p,stdout,stderr = self.program,self.stdout,self.stderr

        p.stdin.close()
        for q,p in ((stdout,p.stdout), (stderr,p.stderr)):
            if q is None:
                continue
            q.mutex.acquire()
            while not p.closed:
                try: p.close()
                except IOError:
                    continue
            q.mutex.release()

        def forever(iterable):
            while len(iterable) > 0:
                for n in iterable:
                    yield n
                del(n)
            return

        # join all monitoring threads, and spin until none of them are alive
        [ x.join() for x in self.__threads]
        for th in forever(self.__threads):
            if not th.is_alive():
                self.__threads.discard(th)
            continue
        return

    def __repr__(self):
        if self.running:
            return '<process running pid:%d>'%( self.id )
        return '<process not-running cmd:"%s">'%( self.commandline )

### interfaces
def spawn(stdout, command, **options):
    """Spawn /command/ with the specified /options/. If program writes anything to it's screen, send it to the stdout function.

    If /stderr/ is defined, call stderr with any error output from the program.
    """
    def update(program, output, error, timeout=1.0):
        while True:
            while program.running:
                try:
                    if program.stderr and not program.stderr.empty():
                        error(program.stderr.get(block=True))
                    output(program.stdout.get(block=True))
                except:
                    import traceback
                    _ = traceback.format_exception( *sys.exc_info() )
                    sys.stderr.write("Unexpected exception in update thread for %r:\n%s"% (program, '\n'.join(_)) )
                    time.sleep(1.0)
                continue
            sys.stderr.write("Update loop for %r attempted termination, spinning at %d intervals:\n%s"% (program, timeout))
            while not program.running: time.sleep(1.0)
        return

    stderr = options.pop('stderr', lambda s: None)
    daemon = options.pop('daemon', True)
    options.setdefault('joined', True)

    program = process(command, **options)

    updater = threading.Thread(target=update, name="thread-%x.update"% program.id, args=(program,stdout,stderr))
    updater.daemon = daemon
    updater.start()

    program.updater = updater   # keep a publically available ref
    return program

if __name__ == '__main__':
    pass
