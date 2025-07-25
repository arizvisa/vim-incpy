let s:PACKAGE_NAME = '__incpy__'
let s:PLUGIN_NAME = trim(s:PACKAGE_NAME, '_')

" Default name of buffer containing interpreter.
let s:WINDOW_NAME = 'Scratch'

" Default file name under home directory to use if $PYTHONSTARTUP is undefined.
let s:PYTHONRC_FILE_NAME = '.pythonrc.py'

" Default window options for plain, old, vanilla vim.
let s:core_window_options = {
\   'buftype': has('terminal')? 'terminal' : 'nofile',
\   'swapfile': v:false,
\   'updatecount': 0,
\   'buflisted': v:false,
\   'bufhidden': 'hide',
\}

" Default window options for neovim, quirks and all.
let s:neo_window_options = {
\   'buftype': 'nofile',
\   'swapfile': v:false,
\   'updatecount': 0,
\   'buflisted': v:false,
\   'bufhidden': 'hide',
\}

" Initialize the options with some reasonable defaults. This function will only
" assign globals that haven't already been assigned by the user.
function! incpy#options#setup()
    let defopts = {}

    let defopts["PackageName"] = s:PACKAGE_NAME
    let defopts["PluginName"] = s:PLUGIN_NAME

    " Set any default options for the plugin that the user missed
    let defopts["Program"] = ""
    let defopts["Echo"] = v:true
    let defopts["OutputFollow"] = v:true
    let defopts["WindowName"] = s:WINDOW_NAME
    let defopts["WindowRatio"] = 1.0/3
    let defopts["WindowPosition"] = "below"
    let defopts["WindowOptions"] = {}
    let defopts["WindowPreview"] = v:false
    let defopts["WindowStartup"] = v:true

    let defopts["Greenlets"] = v:false
    let defopts["Terminal"] = has('terminal') || has('nvim')

    let python_builtins = printf("__import__(%s)", incpy#string#quote_double('builtins'))
    let python_pydoc = printf("__import__(%s)", incpy#string#quote_double('pydoc'))
    let python_sys = printf("__import__(%s)", incpy#string#quote_double('sys'))
    let python_help = join([python_builtins, 'help'], '.')
    let defopts["HelpFormat"] = printf("%s.getpager = lambda: %s.plainpager\ntry:exec(\"%s({0})\")\nexcept SyntaxError:%s(\"{0}\")\n\n", python_pydoc, python_pydoc, escape(python_help, "\"\\"), python_help)

    let defopts["InputStrip"] = function("incpy#python#normalize")
    let defopts["EchoFormat"] = "# >>> {}"
    let defopts["EchoNewline"] = "{}\n"
    let defopts["EvalFormat"] = printf("%s.displayhook(({}))\n", python_sys)
    let defopts["EvalStrip"] = v:false
    let defopts["ExecFormat"] = "{}\n"
    let defopts["ExecStrip"] = v:false

    " If the PYTHONSTARTUP environment-variable exists, then use it. Otherwise,
    " fall back to whatever the script-local variable is set to.
    if exists("$PYTHONSTARTUP")
        let defopts["PythonStartup"] = $PYTHONSTARTUP
    elseif exists("$HOME")
        let defopts["PythonStartup"] = join(split($HOME, '/', v:true) + [s:PYTHONRC_FILE_NAME], '/')
    elseif exists("$USERPROFILE")
        let defopts["PythonStartup"] = join(split($USERPROFILE, '\', v:true) + [s:PYTHONRC_FILE_NAME], '/')
    else
        let defopts["PythonStartup"] = v:null
    endif

    " Set the default window options that the user will override.
    let defopts["CoreWindowOptions"] = has('nvim')? s:neo_window_options : s:core_window_options

    " Iterate through all of the default options checking to see if any are not
    " defined as globals. If any are not, then assign each one as a global.
    for o in keys(defopts)
        if ! exists("g:incpy#{o}")
            let g:incpy#{o} = defopts[o]
        endif
    endfor
endfunction

" Merge the default window options with the a:other and any configured window
" options. The merged result will be returned to the caller as a dictionary.
function! incpy#options#window(other={})
    let core = g:incpy#CoreWindowOptions

    " Initialize our result dictionary with the core window options.
    let result = {}
    for o in keys(core)
        let result[o] = core[o]
    endfor

    " Specially handle the window preview option. This dictionary key isn't an
    " option, but is used to influence the command used to create the window.
    if exists('g:incpy#WindowPreview')
        let result['preview'] = g:incpy#WindowPreview
    endif

    " Merge in any custom window options that were assigned.
    for o in keys(g:incpy#WindowOptions)
        let result[o] = g:incpy#WindowOptions[o]
    endfor

    " Merge in any of the other options that we were given.
    for o in keys(a:other)
        let result[o] = a:other[o]
    endfor
    return result
endfunction
