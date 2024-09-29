import sys, logging, abc, itertools
from . import integer_types, string_types, interface, process, logger

vim, logger = interface.vim, logger.getChild(__name__)

# save initial state
state = tuple(getattr(sys, _) for _ in ['stdin', 'stdout', 'stderr'])

def get_interpreter_frame(*args):
    [frame] = args if args else [sys._getframe()]
    while frame.f_back:
        frame = frame.f_back
    return frame

# interpreter classes
class interpreter(object if sys.version_info.major < 3 else abc.ABC):
    __metaclass__ = abc.ABCMeta

    # methods needed to be implemented by the implementor
    @abc.abstractmethod
    def communicate(self, command, silent=False):
        '''Send the specified command to the currently running interpreter.'''
        raise NotImplementedError

    @abc.abstractmethod
    def start(self, number_or_name):
        '''Start the interpreter within the specified buffer.'''
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self):
        '''Stop the currently running interpreter.'''
        raise NotImplementedError

    # make this thing look kind of like a file
    write = abc.abstractproperty(property())
    writable = abc.abstractproperty(property())
    read = abc.abstractproperty(property())
    readable = abc.abstractproperty(property())
    seek = abc.abstractproperty(property())
    seekable = abc.abstractproperty(property())
    truncate = abc.abstractproperty(property())

class interpreter_with_view(interpreter):
    """
    This base class is responsible for managing the view for an
    interpreter. The view contains the buffer that is modified
    and is responsible for managing the windows that target it.
    """

    def __init__(self):
        self.__view__ = None

    def __repr__(self):
        cls, buffer = self.__class__, self.view.buffer if self.view else None

        buffer_description = "{:d}".format(buffer.number) if buffer else 'missing'
        if self.view and self.view.windows:
            count = vim.newwindow.count()
            return "<{:s} buffer:{:s} ({:s})>".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__]), buffer_description, "{:d}".format(count) if len(self.view.windows) == count else "{:d}/{:d}".format(len(self.view.windows), count))

        count = len(vim.newbuffer.windows(buffer.number)) if buffer else 0
        return "<{:s} buffer:{:s} {:s}>".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__]), buffer_description, "({:d})".format(count) if count else 'hidden')

    # properties needed by each interpreter.
    @property
    def view(self):
        if self.__view__:
            return self.__view__
        cls = self.__class__
        components = [getattr(cls, name, __name__) for name in ['__module__', '__name__'] if hasattr(cls, name)]
        raise vim.error("Unable to access the view for the selected interpreter{:s}.".format(" ({:s})".format('.'.join(filter(None, components))) if components else ''))

    @property
    def buffer(self):
        return self.view.buffer.number

    # forward everything that makes this look like a file to the view
    write = property(fget=lambda self: self.view.write)
    writable = property(fget=lambda self: self.view.writable)
    read = property(fget=lambda self: self.view.read)
    readable = property(fget=lambda self: self.view.readable)
    seek = property(fget=lambda self: self.view.seek)
    seekable = property(fget=lambda self: self.view.seekable)
    truncate = property(fget=lambda self: self.view.truncate)

    @abc.abstractmethod
    def start(self, number_or_name_or_view):
        '''Save or create a view for the specified buffer and return it.'''
        if isinstance(number_or_name_or_view, integer_types):
            buffer = number_or_name_or_view
        elif isinstance(number_or_name_or_view, string_types):
            buffer = vim.newbuffer.new(number_or_name_or_view)

        # if we were given a view as the parameter, then just use it.
        elif isinstance(number_or_name_or_view, interface.multiview):
            self.__view__ = view = number_or_name_or_view
            return view.buffer.number
        else:
            cls = self.__class__
            raise vim.error("Unsupported type ({!s}) cannot be assigned to the view for {:s}.".format(number_or_name_or_view.__class__, '.'.join([getattr(cls, '__module__', __name__), cls.__name__])))

        # use the buffer to create a view and then return its buffer number.
        self.__view__ = view = interface.multiview(buffer)
        return view

class newinternal(interpreter_with_view):
    """
    This class represents an interpreter that uses the internal
    python instance that is started by the editor. It can be
    used to execute python in an arbitrary scope that is specifed
    during instantiation of the class. The parameters for the
    class are the same as the parameters for the "exec" keyword.
    """

    def __init__(self, *context):
        super(newinternal, self).__init__()
        self.logger = logger.getChild('internal')
        self.state = ()

        # validate that we were given a valid number of scopes
        # for executing the python interpreter within.
        if len(context) not in {0, 1, 2, min(sys.version_info.major, 3)}:
            cls = self.__class__
            raise vim.error("Unexpected number of scopes ({:d}) were used to instantiate the {:s} class.".format(len(context), '.'.join([getattr(cls, '__module__', __name__), cls.__name__])))

        # if we were given a scope for executing python, then fill
        # them out so we have enough parameters for calling `exec`.
        elif context:
            default = [scope for scope in itertools.chain([globals(), locals()], [] if sys.version_info.major < 3 else [None])]
            clamped = [scope for scope in itertools.chain(context, default[-len(default) + len(context):])]
            workspace = clamped[:len(default)]

        # if we weren't given any scopes, then we need to figure
        # out ourselves whichever one we'll be interacting with.
        else:
            frame = get_interpreter_frame()
            workspace = [getattr(frame, attribute) for attribute in ['f_globals', 'f_locals']]

        # now we'll assign the scopes that were specified to a
        # private property that we can access if necessary.
        self.__workspace__ = [scope for scope in workspace]

    def start(self, name=''):
        '''Start the internal interpreter by attaching it to a new buffer with the specified name.'''
        view = super(newinternal, self).start(name or vim.gvars['incpy#WindowName'])

        # after creating the view, back up the current stdin, stdout, and stderr.
        self.state = sys.stdin, sys.stdout, sys.stderr

        # notify the user
        self.logger.debug("Redirecting sys.stdin, sys.stdout, and sys.stderr to {!r}.".format(view))

        # add a handler for python output window so that it catches everything
        handler = logging.StreamHandler(view)
        handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT, None))
        self.logger.addHandler(handler)

        # finally we can redirect all the output as was promised.
        _, sys.stdout, sys.stderr = None, view, view
        return True

    def stop(self):
        '''Stop the internal interpreter by detaching it from its associated buffer.'''
        cls = self.__class__
        if not self.state:
            self.logger.fatal("Refusing to stop {:s} as it has not yet been started.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__])))
            return False

        # remove the python output window formatter from the interpreter's logger.
        self.logger.debug("Removing window handler from logger for {:s}.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__])))

        try:
            iterable = (L for L in self.logger.handlers if isinstance(L, logging.StreamHandler) and L.stream == self.view)
            self.logger.removeHandler(next(iterable))

        except StopIteration:
            pass

        # notify the user that we're restoring the original state
        self.logger.debug("Restoring sys.stdin, sys.stdout, and sys.stderr from {:s}.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__])))
        (sys.stdin, sys.stdout, sys.stderr), self.state = self.state, ()
        return True

    def communicate(self, data, silent=False):
        '''Send the specified data as input to the internal interpreter.'''
        echonewline = vim.gvars['incpy#EchoNewline']
        if vim.gvars['incpy#Echo'] and not silent:
            echoformat = vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)
            echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            self.write(echonewline.format(echo))

        # extract the scopes that we were instantiated with
        # and execute the code we were given within them.
        globals, locals, closure = (self.__workspace__ + 3 * [None])[:3]
        exec("exec(data, globals, locals{:s})".format(', closure=closure' if sys.version_info.major >= 3 and sys.version_info.minor >= 11 else ''))

class newexternal(interpreter_with_view):
    """
    This interpreter is responsible for spawning an arbitrary
    process and capturing its output directly into a buffer.
    When instantiating this class, its parameters contain the
    command to execute along with any options for its execution.
    """

    def __init__(self, command, **kwargs):
        super(newexternal, self).__init__()
        self.logger = logger.getChild('external')
        self.instance = None

        self.command = command
        self.command_options = kwargs.get('options', {})

    def __repr__(self):
        res = super(newexternal, self).__repr__()
        if self.instance and self.instance.running:
            return "{:s} {{{!r} {:s}}}".format(res, self.instance, self.command)
        return "{:s} {{{!s}}}".format(res, self.instance)

    def start(self, name=''):
        '''Start the process associated with the external interpreter in a buffer with the specified name.'''
        cls, view = self.__class__, super(newexternal, self).start(name or vim.gvars['incpy#WindowName'])

        self.logger.debug("Spawning process for {:s} in buffer {:d} with command: {:s}.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__]), self.buffer, self.command))
        self.instance = instance = process.spawn(view.write, self.command, **self.command_options)
        self.logger.info("Process {:d} ({:#x}) has been started for {:s}.".format(self.instance.id, self.instance.id, '.'.join([getattr(cls, '__module__', __name__), cls.__name__])))

        # FIXME: worth verifying that the process was started successfully.
        return True

    def stop(self):
        '''Stop the process associated with the external interpreter.'''
        cls = self.__class__
        if not self.instance:
            self.logger.fatal("Refusing to stop process for {:s} which has never been started.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__])))
            return False

        # if the process instance is not running, then there's nothing to do.
        elif not self.instance.running:
            self.logger.fatal("Refusing to stop process for {:s} which has already been terminated.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__]), self.instance))
            return False

        self.logger.info("Killing process {:d} ({:#x}) started by {:s}.".format(self.instance.id, self.instance.id, '.'.join([getattr(cls, '__module__', __name__), cls.__name__])))
        self.instance.stop()
        return True

    def communicate(self, data, silent=False):
        '''Send the specified data as input to the external process.'''
        echonewline = vim.gvars['incpy#EchoNewline']
        if vim.gvars['incpy#Echo'] and not silent:
            echoformat = vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)
            echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            self.write(echonewline.format(echo))
        self.instance.write(data)

class newterminal(interpreter_with_view):
    """
    This interpreter is responsible for spawning an arbitrary
    process as a terminal job which writes its output directly
    into a buffer. This requires the editor to be compiled with
    the "terminal" feature enabled. When instantiating this
    class, the parameters include the command to execute along
    with any options responsible for starting the terminal job.
    """

    def __init__(self, command, **kwargs):
        super(newterminal, self).__init__()

        self.logger = logger.getChild('terminal')
        self.command = command

        # set some reasonable terminal options for the command.
        default_options = {
            "hidden": 1,
            "stoponexit": 'term',
            "term_kill": 'hup',
            "term_finish": "open",
        }

        # update the options with the buffer name and any
        # options that were provided to us by the caller.
        options = {key : value for key, value in default_options.items()}
        options.update(kwargs)
        self.command_options = options

    def __repr__(self):
        res = super(newterminal, self).__repr__()
        return "{:s} {{{!r}}}".format(res, self.command)

    def communicate(self, data, silent=False):
        '''Send the specified data as input to the terminal process.'''
        echonewline = vim.gvars['incpy#EchoNewline']
        if vim.gvars['incpy#Echo'] and not silent:
            echoformat = vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)

            # Terminals don't let you modify or edit the buffer in any way
            #echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            #self.write(echonewline.format(echo))

        vim.terminal.send(self.buffer, data)

    def start(self, name=''):
        '''Start the process associated with the terminal interpreter in a new buffer with the specified name.'''
        options = {key : value for key, value in self.command_options.items()}

        # because python is maintained by fucking idiots
        ignored_env = {'PAGER', 'MANPAGER'}
        filtered_env = {name : '' if name in ignored_env else value for name, value in __import__('os').environ.items() if name not in ignored_env}
        filtered_env['TERM'] = 'emacs'
        #options['env'] = vim.Dictionary(filtered_env)   # because VIM doesn't do what it's told recursively

        # create the new terminal to get the buffer for the process.
        options['term_name'] = name or vim.gvars['incpy#WindowName']
        buffer = vim.terminal.start(self.command, **options)
        return super(newterminal, self).start(buffer)

    def stop(self):
        '''Stop the process associated with the terminal interpreter.'''
        cls, buffer = self.__class__, self.buffer

        # first verify that the job actually exists in the buffer.
        if not vim.terminal.exists(buffer):
            self.logger.fatal("Unable to stop terminal process for {:s} due to its job not being found in buffer {:d}.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__]), self.buffer))
            return False

        # now we can get the process id for the purpose of logging.
        else:
            info = vim.terminal.info(buffer)
            pid = info['process']

        # attempt to stop the job object using the buffer number.
        self.logger.info("Stopping job {:d} ({:#x}) started by {:s}.".format(pid, pid, '.'.join([getattr(cls, '__module__', __name__), cls.__name__])))
        ok = vim.terminal.stop(buffer)
        if not ok:
            raise vim.error("Unexpected error trying to stop job for {:s} using `{:s}`.".format('.'.join([getattr(cls, '__module__', __name__), cls.__name__]), 'job_stop'))

        # verify that the job was actually stopped.
        status = vim.terminal.wait(buffer) or vim.terminal.status(buffer)
        if status != 'finished':
            self.logger.fatal("Unable to stop job in buffer {:d} for {:s} ({:s}).".format(self.buffer, '.'.join([getattr(cls, '__module__', __name__), cls.__name__]), status))
            return False

        self.logger.info("Successfully terminated job {:d} ({:#x}) in buffer {:d} for {:s}.".format(pid, pid, self.buffer, '.'.join([getattr(cls, '__module__', __name__), cls.__name__])))
        return True

class interpreter(object):
    # options that are used for constructing the view
    view_options = ['buffer', 'opt', 'preview', 'tab']

    @classmethod
    def new(cls, *args, **options):
        options.setdefault('buffer', None)
        return cls(*args, **options)

    def __init__(self, **kwds):
        core = {}.__class__(vim.gvars['incpy#CoreWindowOptions'])
        core.update(vim.gvars['incpy#WindowOptions'])
        core.update(kwds.pop('opt', {}))
        kwds.setdefault('preview', vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', vim.tab.getCurrent())
        self.view = interface.view(kwds.pop('buffer', None) or vim.gvars['incpy#WindowName'], core, **kwds)

    def write(self, data):
        """Writes data directly into view"""
        return self.view.write(data)

    def __repr__(self):
        cls = self.__class__
        if self.view.window > -1:
            return "<{:s} buffer:{:d}>".format('.'.join([__name__, cls.__name__]), self.view.buffer.number)
        return "<{:s} buffer:{:d} hidden>".format('.'.join([__name__, cls.__name__]), self.view.buffer.number)

    def attach(self):
        """Attaches interpreter to view"""
        raise NotImplementedError

    def detach(self):
        """Detaches interpreter from view"""
        raise NotImplementedError

    def communicate(self, command, silent=False):
        """Sends commands to interpreter"""
        raise NotImplementedError

    def start(self):
        """Starts the interpreter"""
        raise NotImplementedError

    def stop(self):
        """Stops the interpreter"""
        raise NotImplementedError

class python_internal(interpreter):
    state = None

    def __init__(self, *args, **kwds):
        super(python_internal, self).__init__(**kwds)

        if len(args) not in {0, 1, 2, min(sys.version_info.major, 3)}:
            (lambda source, globals, locals: None)('', *args)
            raise Exception

        elif not args:
            frame = get_interpreter_frame()
            args = [getattr(frame, attribute) for attribute in ['f_globals', 'f_locals']]

        globals, locals = 2 * args if len(args) < 2 else args[:2]
        self.__workspace__ = [globals, locals, None if len(args) < 3 else args[-1]][:min(sys.version_info.major, 3)]

    def attach(self):
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

        _, _, err, logger = self.state

        # remove the python output window formatter from the root logger
        logger.debug("removing window handler from root logger")
        try:
            logger.root.removeHandler(next(L for L in logger.root.handlers if isinstance(L, logging.StreamHandler) and type(L.stream).__name__ == 'view'))
        except StopIteration:
            pass

        logger.warning("detaching internal interpreter from sys.stdin, sys.stdout, and sys.stderr.")

        # notify the user that we're restoring the original state
        logger.debug("restoring sys.stdin, sys.stdout, and sys.stderr from: {!r}".format(self.state))
        (sys.stdin, sys.stdout, sys.stderr, _), self.state = self.state, None

    def communicate(self, data, silent=False):
        echonewline = vim.gvars['incpy#EchoNewline']
        if vim.gvars['incpy#Echo'] and not silent:
            echoformat = vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)
            echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            self.write(echonewline.format(echo))

        globals, locals, closure = (self.__workspace__ + 3 * [None])[:3]
        exec("exec(data, globals, locals{:s})".format(', closure=closure' if sys.version_info.major >= 3 and sys.version_info.minor >= 11 else ''))

    def start(self):
        logger.warning("internal interpreter has already been (implicitly) started")

    def stop(self):
        logger.fatal("unable to stop internal interpreter as it is always running")

# external interpreter (newline delimited)
class external(interpreter):
    instance = None

    @classmethod
    def new(cls, command, **options):
        res = cls(**options)
        [ options.pop(item, None) for item in cls.view_options ]
        res.command, res.options = command, options
        return res

    def attach(self):
        logger.debug("connecting i/o from {!r} to {!r}".format(self.command, self.view))
        self.instance = process.spawn(self.view.write, self.command, **self.options)
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
        echonewline = vim.gvars['incpy#EchoNewline']
        if vim.gvars['incpy#Echo'] and not silent:
            echoformat = vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)
            echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            self.write(echonewline.format(echo))
        self.instance.write(data)

    def __repr__(self):
        res = super(external, self).__repr__()
        if self.instance.running:
            return "{:s} {{{!r} {:s}}}".format(res, self.instance, self.command)
        return "{:s} {{{!s}}}".format(res, self.instance)

    def start(self):
        logger.info("starting process {!r}".format(self.instance))
        self.instance.start()

    def stop(self):
        logger.info("stopping process {!r}".format(self.instance))
        self.instance.stop()

# terminal interpreter
class terminal(external):
    instance = None

    # hacked this in because i'm not sure what external is supposed to be doing
    @property
    def options(self):
        return self.__options
    @options.setter
    def options(self, dict):
        self.__options.update(dict)

    def __init__(self, **kwds):
        core = {}.__class__(vim.gvars['incpy#CoreWindowOptions'])
        core.update(vim.gvars['incpy#WindowOptions'])
        core.update(kwds.pop('opt', {}))

        options = {'hidden': True}
        options.update(core)
        self.__options = options

        kwds.setdefault('preview', vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', vim.tab.getCurrent())
        self.__keywords = kwds
        #self.__view = None
        self.buffer = None

    @property
    def view(self):
        #if self.__view:
        #    return self.__view
        current = vim.window.current()
        #vim.window.select(vim.gvars['incpy#WindowName'])
        #vim.command('terminal ++open ++noclose ++curwin')
        buffer = self.start() if self.buffer is None else self.buffer
        self.__view = res = interface.view(buffer, self.options, **self.__keywords)
        vim.window.select(current)
        return res

    def attach(self):
        """Attaches interpreter to view"""
        view = self.view
        window = view.window
        current = vim.window.current()

        # search to see if window exists, if it doesn't..then show it.
        searched = vim.window.buffer(self.buffer)
        if searched < 0:
            self.view.buffer = self.buffer

        vim.window.select(current)
        # do nothing, always attached

    def detach(self):
        """Detaches interpreter from view"""
        # do nothing, always attached

    def communicate(self, data, silent=False):
        """Sends commands to interpreter"""
        echonewline = vim.gvars['incpy#EchoNewline']
        if vim.gvars['incpy#Echo'] and not silent:
            echoformat = vim.gvars['incpy#EchoFormat']
            lines = data.split('\n')
            iterable = (index for index, item in enumerate(lines[::-1]) if item.strip())
            trimmed = next(iterable, 0)

            # Terminals don't let you modify or edit the buffer in any way
            #echo = '\n'.join(map(echoformat.format, lines[:-trimmed] if trimmed > 0 else lines))
            #self.write(echonewline.format(echo))

        term_sendkeys = vim.Function('term_sendkeys')
        buffer = self.view.buffer
        term_sendkeys(buffer.number, data)

    def start(self):
        """Starts the interpreter"""
        term_start = vim.Function('term_start')

        # because python is maintained by fucking idiots
        ignored_env = {'PAGER', 'MANPAGER'}
        filtered_env = {name : '' if name in ignored_env else value for name, value in __import__('os').environ.items() if name not in ignored_env}
        filtered_env['TERM'] = 'emacs'

        options = vim.Dictionary({
            "hidden": 1,
            "stoponexit": 'term',
            "term_name": vim.gvars['incpy#WindowName'],
            "term_kill": 'hup',
            "term_finish": "open",
            # "env": vim.Dictionary(filtered_env),  # because VIM doesn't do as it's told
        })
        self.buffer = res = term_start(self.command, options)
        return res

    def stop(self):
        """Stops the interpreter"""
        term_getjob = vim.Function('term_getjob')
        job = term_getjob(self.buffer)

        job_stop = vim.Function('job_stop')
        job_stop(job)

        job_status = vim.Function('job_status')
        if job_status(job) != 'dead':
            raise Exception("Unable to terminate job {:d}".format(job))
        return
