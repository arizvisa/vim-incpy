"""
This contains the finders and loaders that can be appended to
the "meta_path" in order to create a set of modules (package)
that are composed of the files within a directory. The purpose
of this is so that we can avoid directly tampering with the
`sys.path` list, and so that we can easily uninstall it when
we are done.

One feature of this module is that it can be read and
executed within an arbitrary namespace, without depending
on any other variables that might be defined. The classes
within this module are compatible with both Py2 and Py3.
"""
import builtins, itertools, os, sys

# Implementation of `exec` that can be treated as a
# function and is compatible with both Py2 and Py3.
def exec_(source, globals=None, locals=None):
    if hasattr(builtins, 'exec'):
        return getattr(builtins, 'exec')(source, globals, locals)
    exec(source, globals, locals)

# Now for the obligatory version checks that assign each
# available class method to the correct implementation.
class python_import_machinery(object):
    """
    This class is a wrapper around the import machinery used by the Python
    interpreter. It does this by implementing a few of the functions from
    the original Py2 "imp" module using the "importlib" functionality that
    was introduced with Python 3.4. On earlier versions of Python, the
    implementation just wraps the relevant functions of the "imp" module.
    """

    # Py2-specific functions for dynamically generating and loading
    # modules. All are based on the original "imp" module functionality.
    @classmethod
    def new_module_py2(cls, fullname):
        return cls.imp.new_module(fullname)

    @classmethod
    def find_module_py2(cls, name, path=None):
        return cls.imp.find_module(name, path)

    @classmethod
    def load_module_py2(cls, name, file, path, description):
        return cls.imp.load_module(name, file, path, description)

    @classmethod
    def load_source_py2(cls, name, path):
        return cls.imp.load_source(name, path)

    @classmethod
    def module_spec_py2(cls, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def module_spec_from_file_py2(cls, name, path):
        raise NotImplementedError

    # Py3-specific functions for dynamically generating and loading
    # modules. These use the new module loader specification format
    # found within the "importlib" module. It (poorly) attempts to
    # load modules exactly how Py2 used to originally load modules.
    @classmethod
    def new_module_py3(cls, fullname):
        spec = cls.importlib.machinery.ModuleSpec(fullname, None)
        module = cls.importlib.util.module_from_spec(spec)
        return module

    @classmethod
    def find_module_py3(cls, name, path=None):
        ext, fucking_paths = 'py', sys.path if path is None else path
        for path in fucking_paths:
            fullpath = os.path.join(path, '.'.join([name, ext]))
            spec = cls.importlib.util.spec_from_file_location(name, fullpath)
            if spec:
                filemode, PY_SOURCE, PY_COMPILED, C_EXTENSION = 'rt', 1, 2, 3
                description = ext, filemode, PY_SOURCE
                return builtins.open(fullpath, filemode), fullpath, description
            continue
        raise ModuleNotFoundError

    @classmethod
    def load_module_py3(cls, name, path):
        spec = cls.importlib.util.spec_from_file_location(name, path)
        module = cls.importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    @classmethod
    def load_source_py3(cls, name, path):
        loader = cls.importlib.machinery.SourceFileLoader(name, path)
        spec = cls.importlib.util.spec_from_loader(loader.name, loader)
        module = cls.importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    @classmethod
    def module_spec_py3(cls, *args, **kwargs):
        return cls.importlib.machinery.ModuleSpec(*args, **kwargs)

    @classmethod
    def module_spec_from_file_py3(cls, name, path):
        return cls.importlib.util.spec_from_file_location(name, path)

    # These assignments are for compatibility with Py2.
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 4):
        import imp
        new_module, find_module, load_module, load_source = new_module_py2, find_module_py2, load_module_py2, load_source_py2
        module_spec, module_spec_from_file = module_spec_py2, module_spec_from_file_py2

    # These next ones map the same functions to their Py3 versions.
    else:
        import importlib, importlib.machinery, importlib.util
        new_module, find_module, load_module, load_source = new_module_py3, find_module_py3, load_module_py3, load_source_py3
        module_spec, module_spec_from_file = module_spec_py3, module_spec_from_file_py3

class vim_plugin_support_loader(object):
    def __init__(self, name, components, path):
        self._name, self._components, self._path = name, components, path
    def get_spec(self):
        PY_SOURCE = 1
        _, ext = os.path.splitext(self._path)
        return ext, 'r', PY_SOURCE
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        with builtins.open(self._path, 'rt') as infile:
            exec_(infile.read(), module.__dict__, module.__dict__)
        return module

class vim_plugin_support_loader_py2(vim_plugin_support_loader):
    def __init__(self, name, components, path):
        self._name, self._components, self._path = name, components, path
    def load_module(self, fullname):
        name, path = '.'.join(itertools.chain([self._name], self._components)), self._path
        #assert(name == fullname), (name, fullname)

        #module = python_import_machinery.load_source(fullname, path)
        with builtins.open(path, 'rt') as stream:
            infile = os.fdopen(os.dup(stream.fileno()))
            #module = python_import_machinery.load_module(name, infile, path, self.get_spec())
            module = python_import_machinery.load_module(fullname, infile, path, self.get_spec())

        dp = os.path.dirname(path)
        if os.path.isdir(dp):
            module.__path__ = [dp]
        return module

class vim_plugin_support_finder(object):
    def __init__(self, path, mapping):
        self._runtime_path = path
        self._mapping = mapping

    # Py2
    def find_module(self, fullname, path=None):
        module, submodule = fullname.split('.', 1) if '.' in fullname else (fullname, '')
        if fullname in self._mapping:
            filename = self._mapping[fullname]
            fp = os.path.join(self._runtime_path, filename)
            if os.path.exists(fp):
                return vim_plugin_support_loader_py2(module, [], fp)
            return None

        elif module in self._mapping:
            package_path, suffix = os.path.splitext(os.path.join(self._runtime_path, self._mapping[module]))
            components = submodule.split('.')
            fp = os.path.join(*itertools.chain([package_path], components[:-1], [''.join(itertools.chain(components[-1:], [suffix]))]))
            dp = os.path.dirname(fp)
            if os.path.exists(fp):
                return vim_plugin_support_loader_py2(module, components, fp)
            return None

        return None

    # Py3
    def find_spec(self, fullname, path, target=None):
        module, submodule = fullname.split('.', 1) if '.' in fullname else (fullname, '')
        if fullname in self._mapping:
            filename = self._mapping[fullname]
            fp = os.path.join(self._runtime_path, filename)
            if not os.path.exists(fp):
                return None

            package, suffix = os.path.splitext(fp)
            attributes = {'is_package': True} if os.path.isdir(package) else {}
            loader = vim_plugin_support_loader(fullname, [], fp)
            return python_import_machinery.module_spec(fullname, loader, **attributes)

        elif module in self._mapping:
            package_path, suffix = os.path.splitext(os.path.join(self._runtime_path, self._mapping[module]))
            components = submodule.split('.')
            fp = os.path.join(*itertools.chain([package_path], components[:-1], [''.join(itertools.chain(components[-1:], [suffix]))]))
            if not os.path.exists(fp):
                return None

            dp = os.path.dirname(fp)
            attributes = {'is_package': True} if os.path.isdir(dp) else {}
            loader = vim_plugin_support_loader(module, components, fp)
            return python_import_machinery.module_spec(fullname, loader, **attributes)

        return None

class object_loader(object):
    """
    This class defines a generic loader that will always return
    the object that it is constructed with as a fake module.
    """
    def __init__(self, state):
        self.state = state
    def create_module(self, spec):
        return self.state
    def exec_module(self, module):
        return module
    def load_module(self, fullname):
        return self.state

class module_loader(object):
    """
    This class defines a loader that will return a module
    with its namespace composed of the provided dictionary.
    """
    def __init__(self, state):
        self.state = state
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.__dict__.update(self.state)
        return module
    def load_module(self, fullname):
        module = python_import_machinery.new_module(fullname)
        module.__dict__.update(self.state)
        return module

class workspace_finder(object):
    """
    This class is a finder and loader that can be appended
    to the `sys.meta_path` list. It essentially allows building
    ephemeral modules that are initialized with a namespace
    that is specified as a dictionary.

    The parameters for its constructor can be a list of
    keywords, representing the module names and their
    namespace, or some number of names followed by the
    dictionary to use for their namespace.
    """
    def __init__(self, *args, **kwds):
        self.modules = {}
        self.objects = {}

        # if there were any regular parameters, then convert them
        # into a dictionary of keywords so that we can group them.
        if args:
            [names, workspace] = args if len(args) > 1 else itertools.chain(args, [None])
            iterable = [names] if isinstance(names, (''.__class__, u''.__class__)) else names
            kwds.update({name : workspace for name in names})

        # iterate through our parameters collecting the instance
        # for each provided object or a dictionary for each module.
        for name, state in kwds.items():
            if isinstance(state, None.__class__):
                self.modules[name] = state or {}
            else:
                self.objects[name] = state
            continue

        # collect a set so that we can look up either by name
        self.available = {name for name in itertools.chain(self.modules, self.objects)}
    def has_loader(self, fullname):
        return fullname in self.available
    def get_loader(self, fullname):
        if fullname in self.modules:
            return module_loader(self.modules[fullname])
        return object_loader(self.objects[fullname])
    def find_module(self, fullname, path=None):
        if self.has_loader(fullname):
            return self.get_loader(fullname)
        return None
    def find_spec(self, fullname, path, target=None):
        if self.has_loader(fullname):
            loader = self.get_loader(fullname)
            return python_import_machinery.module_spec(fullname, loader)
        return None

class vim_plugin_packager(object):
    """
    This class is intended to be used as a "meta_path" object
    that can wrap any number of finders and bury them behind
    a module with a specified name. This way all modules
    returned by the finders that it was instantiated with
    can be compartmentalized behind a single package.

    The base package generated by this "meta_path" object can also
    be constructed with a custom namespace specified as a dictionary.
    """
    def __init__(self, name, finders, namespace=None):
        self._name = name
        self._finders = [finder for finder in finders]
        self._namespace = namespace or {}

    class package_loader_py2(object):
        def __init__(self, discard, original):
            self._discard, self._original = discard, original
        def __getattr__(self, attribute):
            return getattr(self._original, attribute)
        def load_module(self, fullname):
            length, components = len(self._discard), fullname.split('.')
            if components[:length] != self._discard:
                raise ImportError
            #return self._original.load_module('.'.join(components[length:]))
            return self._original.load_module(fullname)

    def choose_finder(self, components, path):
        fullname = '.'.join(components)
        for finder in self._finders:
            loader = finder.find_module(fullname, path)
            if loader:
                return self.package_loader_py2([self._name], loader)
            continue
        return None

    def find_module(self, fullname, path=None):
        module, submodule = fullname.split('.', 1) if '.' in fullname else (fullname, '')
        if fullname in {self._name}:
            return self
        elif module in {self._name}:
            components = submodule.split('.')
            return self.choose_finder(components, path)
        return None

    def load_module(self, fullname):
        module = sys.modules[fullname] = python_import_machinery.new_module(fullname)
        module.__dict__.update(self._namespace)
        module.__dict__.setdefault('__path__', [])
        return module

    def wrap_spec(self, spec):
        name, loader, origin, loader_state = (getattr(spec, attribute) for attribute in ['name', 'loader', 'origin', 'loader_state'])
        is_package = spec.submodule_search_locations is not None

        fullname = '.'.join([self._name, name])

        res = python_import_machinery.module_spec(fullname, loader, origin=origin, loader_state=loader_state, is_package=is_package)
        res.submodule_search_locations = spec.submodule_search_locations
        res.has_location = spec.has_location
        res.cached = spec.cached
        return res

    def choose_spec(self, components, path, target):
        fullname = '.'.join(components)
        for finder in self._finders:
            spec = finder.find_spec(fullname, path, target)
            if spec:
                return self.wrap_spec(spec)
            continue
        return None

    def find_spec(self, fullname, path, target=None):
        module, submodule = fullname.split('.', 1) if '.' in fullname else (fullname, '')
        if fullname in {self._name}:
            return python_import_machinery.module_spec(fullname, self, is_package=True)
        elif module in {self._name}:
            components = submodule.split('.')
            return self.choose_spec(components, path, target)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__dict__.update(self._namespace)
        return module
