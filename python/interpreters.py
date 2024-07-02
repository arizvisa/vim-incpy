import sys, builtins, six, logging
from . import incpy, interface
from .incpy import buffer, spawn

internal = interface.internal
vim = interface.vim

# save initial state
state = tuple(getattr(sys, _) for _ in ['stdin', 'stdout', 'stderr'])
logger = logging.getLogger('incpy').getChild('vim')

# interpreter classes
class interpreter(object):
    # options that are used for constructing the view
    view_options = ['buffer', 'opt', 'preview', 'tab']

    @classmethod
    def new(cls, **options):
        options.setdefault('buffer', None)
        return cls(**options)

    def __init__(self, **kwds):
        opt = {}.__class__(vim.gvars['incpy#CoreWindowOptions'])
        opt.update(vim.gvars['incpy#WindowOptions'])
        opt.update(kwds.pop('opt', {}))
        kwds.setdefault('preview', vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', internal.tab.getCurrent())
        self.view = interface.view(kwds.pop('buffer', None) or vim.gvars['incpy#WindowName'], opt, **kwds)

    def write(self, data):
        """Writes data directly into view"""
        return self.view.write(data)

    def __repr__(self):
        if self.view.window > -1:
            return "<__incpy__.{:s} buffer:{:d}>".format(self.__class__.__name__, self.view.buffer.number)
        return "<__incpy__.{:s} buffer:{:d} hidden>".format(self.__class__.__name__, self.view.buffer.number)

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

class interpreter_python_internal(interpreter):
    state = None

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
        exec(data, globals())   # FIXME: need the namespace to write things to

    def start(self):
        logger.warning("internal interpreter has already been (implicitly) started")

    def stop(self):
        logger.fatal("unable to stop internal interpreter as it is always running")

# external interpreter (newline delimited)
class interpreter_external(interpreter):
    instance = None

    @classmethod
    def new(cls, command, **options):
        res = cls(**options)
        [ options.pop(item, None) for item in cls.view_options ]
        res.command, res.options = command, options
        return res

    def attach(self):
        logger.debug("connecting i/o from {!r} to {!r}".format(self.command, self.view))
        self.instance = spawn(self.view.write, self.command, **self.options)
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
        res = super(interpreter_external, self).__repr__()
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
class interpreter_terminal(interpreter_external):
    instance = None

    # hacked this in because i'm not sure what interpreter_external is supposed to be doing
    @property
    def options(self):
        return self.__options
    @options.setter
    def options(self, dict):
        self.__options.update(dict)

    def __init__(self, **kwds):
        self.__options = {'hidden': True}
        opt = {}.__class__(vim.gvars['incpy#CoreWindowOptions'])
        opt.update(vim.gvars['incpy#WindowOptions'])
        opt.update(kwds.pop('opt', {}))
        self.__options.update(opt)

        kwds.setdefault('preview', vim.gvars['incpy#WindowPreview'])
        kwds.setdefault('tab', internal.tab.getCurrent())
        self.__keywords = kwds
        #self.__view = None
        self.buffer = None

    @property
    def view(self):
        #if self.__view:
        #    return self.__view
        current = internal.window.current()
        #internal.window.select(vim.gvars['incpy#WindowName'])
        #vim.command('terminal ++open ++noclose ++curwin')
        buffer = self.start() if self.buffer is None else self.buffer
        self.__view = res = interface.view(buffer, self.options, **self.__keywords)
        internal.window.select(current)
        return res

    def attach(self):
        """Attaches interpreter to view"""
        view = self.view
        window = view.window
        current = internal.window.current()

        # search to see if window exists, if it doesn't..then show it.
        searched = internal.window.buffer(self.buffer)
        if searched < 0:
            self.view.buffer = self.buffer

        internal.window.select(current)
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

# spawn interpreter requested by user
_ = __incpy__.vim.gvars["incpy#Program"]
opt = {'winfixwidth':True, 'winfixheight':True} if __incpy__.vim.gvars["incpy#WindowFixed"] > 0 else {}
try:
    if __incpy__.vim.eval('has("terminal")') and len(_) > 0:
        __incpy__.cache = __incpy__.interpreter_terminal.new(_, opt=opt)
    elif len(_) > 0:
        __incpy__.cache = __incpy__.interpreter_external.new(_, opt=opt)
    else:
        __incpy__.cache = __incpy__.interpreter_python_internal.new(opt=opt)

except Exception:
    __incpy__.logger.fatal("error starting external interpreter: {:s}".format(_), exc_info=True)
    __incpy__.logger.warning("falling back to internal python interpreter")
    __incpy__.cache = __incpy__.interpreter_python_internal.new(opt=opt)
del(opt)

# create it's window, and store the buffer's id
view = __incpy__.cache.view
__incpy__.vim.gvars['incpy#BufferId'] = view.buffer.number
view.create(__incpy__.vim.gvars['incpy#WindowPosition'], __incpy__.vim.gvars['incpy#WindowRatio'])

# delete our temp variable
del(view)
