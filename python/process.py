import sys, functools, itertools, operator
import os, codecs, weakref, time, itertools, shlex

from . import integer_types, string_types, reraise, logger
logger = logger.getChild(__name__)

try:
    # make sure the user has selected the gevent-based version by importing gevent
    # before actually importing this module
    if 'gevent' not in sys.modules:
        raise ImportError

    # FIXME: there's for sure a better way to accomplish this by using a lwt
    #        for monitoring the target process. this way we can implement a
    #        timeout if the monitor'd pipes don't produce any data in time.
    #        if this is the case, then we can just swap back to the main thread
    #        until the next time we're shuffling.
    import gevent
    HAS_GEVENT = 1
    logger.info('the gevent module was discovered within the current environment. using the greenlet variation of spawn.')

    # wrapper around greenlet since my instance of gevent.threading doesn't include a Thread class for some reason.
    class Thread(object):
        def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
            if group is not None:
                raise AssertionError
            f = target or (lambda *a,**k:None)
            self.__greenlet = res = gevent.spawn(f, *args, **(kwargs or {}))
            self.__name = name or "greenlet_{identity:x}({name:s}".format(name=f.__name__, identity=id(res))
            self.__daemonic = False
            self.__verbose = True

        def start(self):
            return self.__greenlet.start()
        def stop(self):
            return self.__greenlet.stop()

        def join(self, timeout=None):
            return self.__greenlet.join(timeout)

        is_alive = isAlive = lambda self: self.__greenlet.started and not self.__greenlet.ready()
        isDaemon = lambda self: self.__daemon
        setDaemon = lambda self, daemonic: setattr(self, '__daemonic', daemonic)
        getName = lambda self: self.__name
        setName = lambda self, name: setattr(self, '__name', name)

        daemon = property(fget=isDaemon, fset=setDaemon)
        ident = name = property(fget=setName, fset=setName)

    class Asynchronous:
        import gevent.queue, gevent.event, gevent.subprocess
        Thread, Queue, Event = map(staticmethod, (Thread, gevent.queue.Queue, gevent.event.Event))
        spawn, spawn_options = map(staticmethod, (gevent.subprocess.Popen, gevent.subprocess))

except ImportError:
    HAS_GEVENT = 0
    logger.info('the gevent module was not found within the current environment. using the thread-based variation of spawn.')

    class Asynchronous:
        import threading
        Thread, Event = map(staticmethod, (threading.Thread, threading.Event))

        import subprocess
        spawn, spawn_options = map(staticmethod, (subprocess.Popen, subprocess))

        # Try importing with Python3's name first
        try:
            import queue as Queue

        # Otherwise we'll try Python2's name
        except ImportError:
            import Queue

        Queue, QueueEmptyException = map(staticmethod, (Queue.Queue, Queue.Empty))

### asynchronous process monitor

# monitoring an external process' i/o via threads/queues
class process(object):
    """Spawns a program along with a few monitoring threads for allowing asynchronous(heh) interaction with a subprocess.

    mutable properties:
    program -- Asynchronous.spawn result
    commandline -- Asynchronous.spawn commandline
    eventWorking -- Asynchronous.Event() instance for signalling task status to monitor threads
    stdout,stderr -- callables that are used to process available work in the taskQueue

    properties:
    id -- subprocess pid
    running -- returns true if process is running and monitor threads are workingj
    working -- returns true if monitor threads are working
    threads -- list of threads that are monitoring subprocess pipes
    taskQueue -- Asynchronous.Queue() instance that contains work to be processed
    exceptionQueue -- Asynchronous.Queue() instance containing exceptions generated during processing
    (process.stdout, process.stderr)<Queue> -- Queues containing output from the spawned process.
    """

    program = None              # Asynchronous.spawn result
    id = property(fget=lambda self: self.program and self.program.pid or -1)
    running = property(fget=lambda self: False if self.program is None else self.program.poll() is None)
    working = property(fget=lambda self: self.running and not self.eventWorking.is_set())
    threads = property(fget=lambda self: list(self.__threads__))
    updater = property(fget=lambda self: self.__updater__)

    taskQueue = property(fget=lambda self: self.__taskQueue)
    exceptionQueue = property(fget=lambda self: self.__exceptionQueue)

    encoding = property(fget=lambda self: self.codec.name)

    def __init__(self, command, **kwds):
        """Creates a new instance that monitors Asynchronous.spawn(`command`), the created process starts in a paused state.

        Keyword options:
        env<dict> = os.environ -- environment to execute program with
        cwd<str> = os.getcwd() -- directory to execute program  in
        shell<bool> = True -- whether to treat program as an argument to a shell, or a path to an executable
        show<bool> = False -- if within a windowed environment, open up a console for the process.
        paused<bool> = False -- if enabled, then don't start the process until .start() is called
        timeout<float> = -1 -- if positive, then raise a Asynchronous.Empty exception at the specified interval.
        """
        ## default properties
        self.__updater__ = None
        self.__threads__ = weakref.WeakSet()
        self.__kwds = kwds

        args = shlex.split(command) if isinstance(command, string_types) else command[:]
        command = args.pop(0)
        self.command = command, args[:]

        self.eventWorking = Asynchronous.Event()
        self.__taskQueue = Asynchronous.Queue()
        self.__exceptionQueue = Asynchronous.Queue()

        self.codec = codecs.lookup(kwds.get('encoding', 'iso8859-1' if sys.getdefaultencoding() == 'ascii' else sys.getdefaultencoding()))
        self.stdout = kwds.pop('stdout')
        self.stderr = kwds.pop('stderr')

        ## start the process
        not kwds.get('paused', False) and self.start()

    def start(self, **options):
        '''Start the command with the requested `options`.'''
        if self.running:
            raise OSError("Process {:d} is still running.".format(self.id))
        if self.updater or len(self.threads):
            raise OSError("Process {:d} management threads are still running.".format(self.id))

        ## copy our default options into a dictionary
        kwds = self.__kwds.copy()
        kwds.update(options)

        env = kwds.get('env', os.environ)
        cwd = kwds.get('cwd', os.getcwd())
        shell = kwds.get('shell', False)
        stdout, stderr = options.pop('stdout', self.stdout), options.pop('stderr', self.stderr)

        ## spawn our subprocess using our new outputs
        self.program = process.subprocess([self.command[0]] + self.command[1], cwd, env, joined=(stderr is None) or stdout == stderr, shell=shell, show=kwds.get('show', False))
        self.eventWorking.clear()

        ## monitor program's i/o
        self.__start_monitoring(stdout, stderr)
        self.__start_updater(timeout=kwds.get('timeout', -1))

        ## start monitoring
        self.eventWorking.set()
        return self

    def __start_updater(self, daemon=True, timeout=0):
        '''Start the updater thread. **used internally**'''

        ## define the closure that wraps our co-routines
        def task_exec(emit, data):
            if hasattr(emit, 'send'):
                res = emit.send(data)
                res and P.write(res)
            else: emit(data)

        ## define the closures that block on the specified timeout
        def task_get_timeout(P, timeout):
            try:
                emit, data = P.taskQueue.get(block=True, timeout=timeout)
            except Asynchronous.QueueEmptyException:
                _, _, tb = sys.exc_info()
                P.exceptionQueue.put(StopIteration, StopIteration(), tb)
                return ()
            return emit, data

        def task_get_notimeout(P, timeout):
            return P.taskQueue.get(block=True)
        task_get = task_get_timeout if timeout > 0 else task_get_notimeout

        ## define the closure that updates our queues and results
        def update(P, timeout):
            P.eventWorking.wait()
            while P.eventWorking.is_set():
                res = task_get(P, timeout)
                if not res: continue
                emit, data = res

                try:
                    task_exec(emit, data)
                except StopIteration:
                    P.eventWorking.clear()
                except:
                    P.exceptionQueue.put(sys.exc_info())
                finally:
                    hasattr(P.taskQueue, 'task_done') and P.taskQueue.task_done()
                continue
            return

        ## actually create and start our update threads
        self.__updater__ = updater = Asynchronous.Thread(target=update, name="thread-{:x}.update".format(self.id), args=(self, timeout))
        updater.daemon = daemon
        updater.start()
        return updater

    def __make_reader(self, pipe, **parameters):
        '''Return an iterator that decodes data from pipe using the current encoding.'''
        decoder = self.codec.incrementaldecoder(**parameters)

        # keep processing bytes and feeding them to our decoder. if the pipe
        # is closed during this process, then that's ok and we can just leave.
        bytereader = iter(functools.partial(pipe.read, 1), b'')
        while not pipe.closed:
            result = decoder.decode(next(bytereader))
            if result:
                yield result
            continue
        return

    def __start_monitoring(self, stdout, stderr=None):
        '''Start monitoring threads. **used internally**'''
        name = "thread-{:x}".format(self.program.pid)

        ## create monitoring threads (coroutines)
        params = dict(errors='replace')
        if stderr:
            out_pair = stdout, self.__make_reader(self.program.stdout, **params)
            err_pair = stderr, self.__make_reader(self.program.stderr, **params)
            res = process.monitorGenerator(self.taskQueue, out_pair, err_pair, name=name)
        else:
            out_pair = stdout, self.__make_reader(self.program.stdout, **params)
            res = process.monitorGenerator(self.taskQueue, out_pair, name=name)

        ## attach a friendly method that allows injection of data into the monitor
        res = list(res)
        for t, q in res: t.send = q.send
        threads, senders = zip(*res)

        ## update our set of threads for destruction later
        self.__threads__.update(threads)

        ## set everything off
        for t in threads: t.start()

    @staticmethod
    def subprocess(program, cwd, environment, joined, shell=(os.name == 'nt'), show=False):
        '''Create a subprocess using Asynchronous.spawn.'''
        stderr = Asynchronous.spawn_options.STDOUT if joined else Asynchronous.spawn_options.PIPE

        ## collect our default options for calling Asynchronous.spawn (subprocess.Popen)
        options = dict(stdin=Asynchronous.spawn_options.PIPE, stdout=Asynchronous.spawn_options.PIPE, stderr=stderr)
        options.update(dict(universal_newlines=False) if sys.version_info.major < 3 else dict(text=False))
        if os.name == 'nt':
            options['startupinfo'] = si = Asynchronous.spawn_options.STARTUPINFO()
            si.dwFlags = Asynchronous.spawn_options.STARTF_USESHOWWINDOW
            si.wShowWindow = show if show else Asynchronous.spawn_options.SW_HIDE
            options['creationflags'] = cf = Asynchronous.spawn_options.CREATE_NEW_CONSOLE if show else 0
            options['close_fds'] = False
            options.update(dict(close_fds=False, startupinfo=si, creationflags=cf))
        else:
            options['close_fds'] = True
        options['bufsize'] = 0
        options['cwd'] = cwd
        options['env'] = environment
        options['shell'] = shell

        ## split our arguments out if necessary
        command = shlex.split(program) if isinstance(program, string_types) else program[:]

        ## finally hand it off to subprocess.Popen
        try: return Asynchronous.spawn(command, **options)
        except OSError: raise OSError("Unable to execute command: {!r}".format(command))

    @staticmethod
    def monitorPipe(q, target, *more, **options):
        """Attach a coroutine to a monitoring thread for stuffing queue `q` with data read from `target`.

        The tuple `target` is composed of two values, `id` and `pipe`.

        Yields a list of (thread, coro) tuples given the arguments provided.
        Each thread will read from `pipe`, and stuff the value combined with `id` into `q`.
        """
        def stuff(q, *key):
            while True:
                item = (yield),
                q.put(key + item)
            return

        for id, pipe in itertools.chain([target], more):
            res, name = stuff(q, id), "{:s}<{!r}>".format(options.get('name', ''), id)
            yield process.monitor(next(res) or res.send, pipe, name=name), res
        return

    @staticmethod
    def monitorGenerator(q, target, *more, **options):
        """Attach a coroutine to a monitoring thread for stuffing queue `q` with data read from `target`.

        The tuple `target` is composed of two values, `id` and `generator`.

        Yields a list of (thread, coro) tuples given the arguments provided.
        Each thread will consume `generator`, and stuff the result paired with `id` into `q`.
        """
        def stuff(q, *key):
            while True:
                item = (yield),
                q.put(key + item)
            return

        for id, reader in  itertools.chain([target], more):
            res, name = stuff(q, id), "{:s}<{!r}>".format(options.get('name', ''), id)
            yield process.monitor_reader(next(res) or res.send, reader, name=name), res
        return

    @staticmethod
    def monitor(send, pipe, blocksize=1, daemon=True, name=None):
        """Spawn a thread that reads `blocksize` bytes from `pipe` and dispatches it to `send`

        For every single byte, `send` is called. The thread is named according to
        the `name` parameter.

        Returns the monitoring Asynchronous.Thread instance
        """

        # FIXME: if we can make this asychronous on windows, then we can
        #        probably improve this significantly by either watching for
        #        a newline (newline buffering), or timing out if no data was
        #        received after a set period of time. so this way we can
        #        implement this in a lwt, and simply swap into and out-of
        #        shuffling mode.
        def shuffle(send, pipe):
            while not pipe.closed:
                # FIXME: would be nice if python devers implemented support for
                # reading asynchronously or a select.select from an anonymous pipe.
                data = pipe.read(blocksize)
                if len(data) == 0:
                    # pipe.read syscall was interrupted. so since we can't really
                    # determine why (cause...y'know..python), stop dancing so
                    # the parent will actually be able to terminate us
                    break
                [ send(item) for item in data ]
            return

        ## create our shuffling thread
        if name:
            truffle = Asynchronous.Thread(target=shuffle, name=name, args=(send, pipe))
        else:
            truffle = Asynchronous.Thread(target=shuffle, args=(send, pipe))

        ## ..and set its daemonicity
        truffle.daemon = daemon
        return truffle

    @staticmethod
    def monitor_reader(sender, reader, daemon=True, name=None):
        """Spawn a thread that reads `blocksize` bytes from `pipe` and dispatches it to `send`

        For every single byte, `send` is called. The thread is named according to
        the `name` parameter.

        Returns the monitoring Asynchronous.Thread instance
        """

        def shuffle(sender, reader):
            for block in reader:
                [ sender(item) for item in block ]
            return

        ## create our shuffling thread
        if name:
            truffle = Asynchronous.Thread(target=shuffle, name=name, args=(sender, reader))
        else:
            truffle = Asynchronous.Thread(target=shuffle, args=(sender, reader))

        ## ..and set its daemonicity
        truffle.daemon = daemon
        return truffle

    def __format_process_state(self):
        if self.program is None:
            return "Process \"{!r}\" {:s}.".format(self.command[0], 'was never started')
        res = self.program.poll()
        return "Process {:d} {:s}".format(self.id, 'is still running' if res is None else "has terminated with code {:d}".format(res))

    def write(self, data):
        '''Write `data` directly to program's stdin.'''
        if self.running and not self.program.stdin.closed:
            if self.updater and self.updater.is_alive():
                encoded, count = self.codec.encode(data)
                return self.program.stdin.write(encoded)
            raise IOError("Unable to write to stdin for process {:d}. Updater thread has prematurely terminated.".format(self.id))
        raise IOError("Unable to write to stdin for process. {:s}.".format(self.__format_process_state()))

    def close(self):
        '''Closes stdin of the program.'''
        if self.running and not self.program.stdin.closed:
            return self.program.stdin.close()
        raise IOError("Unable to close stdin for process. {:s}.".format(self.__format_process_state()))

    def signal(self, signal):
        '''Raise a signal to the program.'''
        if self.running:
            return self.program.send_signal(signal)
        raise IOError("Unable to raise signal {!r} to process. {:s}.".format(signal, self.__format_process_state()))

    def exception(self):
        '''Grab an exception if there's any in the queue.'''
        if self.exceptionQueue.empty(): return
        res = self.exceptionQueue.get()
        hasattr(self.exceptionQueue, 'task_done') and self.exceptionQueue.task_done()
        return res

    def wait(self, timeout=0.0):
        '''Wait a given amount of time for the process to terminate.'''
        if self.program is None:
            raise RuntimeError("Program {!r} is not running.".format(self.command[0]))

        ## if we're not running, then return the result that we already received
        if not self.running:
            return self.program.returncode

        self.updater.is_alive() and self.eventWorking.wait()

        ## spin the cpu until we timeout
        if timeout:
            t = time.time()
            while self.running and self.eventWorking.is_set() and time.time() - t < timeout:
                if not self.exceptionQueue.empty():
                    res = self.exception()
                    reraise(res[0], res[1], res[2])
                continue
            return self.program.returncode if self.eventWorking.is_set() else self.__terminate()

        ## return the program's result

        # XXX: doesn't work correctly with PIPEs due to pythonic programmers' inability to understand os semantics

        while self.running and self.eventWorking.is_set():
            if not self.exceptionQueue.empty():
                res = self.exception()
                reraise(res[0], res[1], res[2])
            continue    # ugh...poll-forever (and kill-cpu) until program terminates...

        if not self.eventWorking.is_set():
            return self.__terminate()
        return self.program.returncode

    def stop(self):
        self.eventWorking.clear()
        return self.__terminate()

    def __terminate(self):
        '''Sends a SIGKILL signal and then waits for program to complete.'''
        pid = self.program.pid
        try:
            self.program.kill()
        except OSError as e:
            logger.fatal("{:s}.__terminate : Exception {!r} was raised while trying to kill process {:d}. Terminating its management threads regardless.".format('.'.join((__name__, self.__class__.__name__)), e, pid), exc_info=True)
        finally:
            while self.running: continue

        self.__stop_monitoring()
        if self.exceptionQueue.empty():
            return self.program.returncode

        res = self.exception()
        reraise(res[0], res[1], res[2])

    def __stop_monitoring(self):
        '''Cleanup monitoring threads.'''
        P = self.program
        if P.poll() is None:
            raise RuntimeError("Unable to stop monitoring while process {!r} is still running.".format(P))

        ## stop the update thread
        self.eventWorking.clear()

        ## forcefully close pipes that still open (this should terminate the monitor threads)

        # also, this fixes a resource leak since python doesn't do this on subprocess death
        for p in (P.stdin, P.stdout, P.stderr):
            while p and not p.closed:
                try: p.close()
                except: pass
            continue

        ## join all monitoring threads

        # XXX: when cleaning up, this module disappears despite there still
        #      being a reference for some reason
        import operator

        # XXX: there should be a better way to block until all threads have joined
        [ th.join() for th in self.threads ]

        # now spin until none of them are alive
        while len(self.threads) > 0:
            for th in self.threads[:]:
                if not th.is_alive(): self.__threads__.discard(th)
                del(th)
            continue

        ## join the updater thread, and then remove it
        self.taskQueue.put(None)
        self.updater.join()
        if self.updater.is_alive():
            raise AssertionError
        self.__updater__ = None
        return

    def __repr__(self):
        ok = self.exceptionQueue.empty()
        state = "running pid:{:d}".format(self.id) if self.running else "stopped cmd:{!r}".format(self.command[0])
        threads = [
            ('updater', 0 if self.updater is None else self.updater.is_alive()),
            ('input/output', len(self.threads))
        ]
        return "<process {:s}{:s} threads{{{:s}}}>".format(state, (' !exception!' if not ok else ''), ' '.join("{:s}:{:d}".format(n, v) for n, v in threads))

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
    if hasattr(stdout, 'send'):
        res = next(stdout)
        res and P.write(res)
    if hasattr(stderr, 'send'):
        res = next(stderr)
        res and P.write(res)

    # spawn the sub-process
    return process(command, stdout=stdout, stderr=stderr, **options)
