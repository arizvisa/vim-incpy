import vim as _vim,exceptions,threading

# vim wrapper
class vim(object):
    class _accessor(object):
        def __init__(self, result):
            self.result = result

        def __get__(self, obj, objtype):
            return self.result

        def __set__(self, obj, val):
            self.result = val

    _error = _vim.error
    class error(exceptions.Exception):
        """because vim is using old-style exceptions based on str"""

    buffers = _accessor(_vim.buffers)
    current = _accessor(_vim.current)

    if (_vim.eval('has("clientserver")')) and False:
        @classmethod
        def command(cls, string):
            escape = ''*16
            cmd = string.replace('"', r'\"')
            return _vim.command('call remote_send(v:servername, "%s:%s\n")'% (escape,cmd))

        @classmethod
        def eval(cls, string):
            #return _vim.eval(string)
            cmd = string.replace('"', r'\"')
            return _vim.eval('remote_expr(v:servername, "%s")'% cmd)

    else:
        @classmethod
        def command(cls, string):
            return _vim.command(string)

        @classmethod
        def eval(cls, string):
            return _vim.eval(string)

# wrapper around vim buffer object
class buffer(object):
    """vim buffer management"""
    ## instance scope
    def __init__(self, buffer):
        assert type(buffer) == type(vim.current.buffer)
        self.buffer = buffer
        #self.writing = threading.Lock()
    def __del__(self):
        self.__destroy(self.buffer)

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
        if vim.eval('v:dying'):
            return
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
        #self.writing.acquire()
        result = iter(data.split('\n'))
        self.buffer[-1] += result.next()
        [self.buffer.append(_) for _ in result]
        #self.writing.release()

    def clear(self):
        #self.writing.acquire()
        self.buffer[:] = ['']
        #self.writing.release()

# monitoring an external process via a thread
import os,signal,threading,Queue,subprocess,time
class spawn(object):
    """Spawns a program along with a few monitoring threads.

    Provides stdout and stderr in the form of Queue.Queue objects to allow for asynchronous reading.
    """

    program = None              # subprocess.Popen object
    stdout,stderr = None,None   # queues containing stdout and stderr
    id = property(fget=lambda s: s.program.pid)
    running = property(fget=lambda s: False if s.program is None else s.program.poll() is None)

    def __init__(self, command, **kwds):
        # process
        env = kwds.get('env', os.environ)
        cwd = kwds.get('cwd', os.getcwd())
        joined = kwds.get('joined', True)
        newlines = kwds.get('newlines', True)
        shell = kwds.get('shell', False)
        self.commandline = command
        self.program = program = self.__newprocess(command, cwd, env, newlines, joined=joined, shell=shell)

        ## monitor threads (which aren't important if python didn't suck with both threads and gc)
        threads = []
        t,stdout = spawn.monitorPipe('thread-%x-stdout'% program.pid, program.stdout)
        threads.append(t)
        if not joined:
            t,stderr = spawn.monitorPipe('thread-%x-stderr'% program.pid, program.stderr)
            threads.append(t)
        else:
            stderr = None
        self.__threads = threads

        # queues containing stdout and stderr
        self.stdout,self.stderr = stdout,stderr

        # set things off
        for t in threads:
            t.start()

    def __newprocess(self, program, cwd, environment, newlines, joined, shell=True):
        stderr = subprocess.STDOUT if joined else subprocess.PIPE
        if os.name == 'nt':
            si = subprocess.STARTUPINFO()
            si.dwFlags = subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            return subprocess.Popen(program, universal_newlines=newlines, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, close_fds=False, startupinfo=si, cwd=cwd, env=environment)
        return subprocess.Popen(program, universal_newlines=newlines, shell=shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, close_fds=True, cwd=cwd, env=environment)
    
    @staticmethod
    def monitorPipe(id, pipe, blocksize=1):
        """Create a monitoring thread that stuffs data from a pipe into a queue.

        Returns a (threading.Thread, Queue.Queue)
        (Queues are the only python object that allow you to timeout if data isn't currently available)
        """

        def shuffle(queue, pipe):
            while not pipe.closed:
                data = pipe.read(blocksize)
                assert len(data) > 0
                queue.put(data)
            return

        q = Queue.Queue()   # XXX: this should be a multiprocessing.Pipe, but i've had many a problems with that module
        if id is None:
            monitorThread = threading.Thread(target=shuffle, args=(q,pipe))
        else:
            monitorThread = threading.Thread(target=shuffle, name=id, args=(q,pipe))
        monitorThread.daemon = True
        return monitorThread,q

    def write(self, data):
        """Write data directly to program's stdin"""
        if self.running:
            return self.program.stdin.write(data)

        pid,result = self.program.pid,self.program.poll()
        raise IOError('Unable to write to terminated process %d. Process terminated with a returncode of %d'% (pid,result))

    def signal(self, signal):
        """Send a signal to the program"""
        if self.running:
            return self.program.send_signal(signal)

        pid,result = self.program.pid,self.program.poll()
        raise IOError('Unable to signal terminated process %d. Process terminated with a returncode of %d'% (pid,result))

    def wait(self, timeout=0.0):
        """Wait for a process to terminate"""
        program = self.program

        if timeout:
            t = time.time()
            while t + timeout > time.time():        # spin until we timeout
                if program.poll() is not None:
                    return program.returncode
                continue
            return None

        return program.wait()

    def stop(self):
        """Sends a SIGKILL signal and then waits for program to complete"""
        if not self.running:
            self.stop_monitoring()
            return self.program.poll()

        p = self.program
        p.kill()
        result = p.wait()
        self.stop_monitoring()
        self.program = None
        return result

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
        [ x.join() for x in self.__threads]

    def __repr__(self):
        if self.running:
            return '<spawn running pid:%d>'%( self.id )
        return '<spawn not-running cmd:"%s">'%( self.commandline )

### interfaces
import threading
def vimspawn(buf, command, **kwds):
    def update(program, frontend):
        stdout,stderr = program.stdout,program.stderr
        while program.running:
            out = stdout.get(block=True)
            frontend.write(out)
            #out = ''
            #while not stdout.empty():
            #    out += stdout.get()
            #if out:
            #    frontend.write(out)
            #continue
        return

    kwds.setdefault('joined', True)
    program = spawn(command, **kwds)
    updater = threading.Thread(target=update, name="%x-update"% program.id, args=(program,buf,))
    updater.daemon = True
    updater.start()
    program.updater = updater
    return program

if __name__ == '__main__':
    pass
