" incremental-python 3.0
" based on an idea that bniemczyk@gmail.com had
" thanks to ccliver@gmail.org for his input
" thanks to Tim Pope <vimNOSPAM@tpope.info> for pointing out preview windows
"
" requires vim to be compiled w/ python support. I noticed that most of my
" python development consisted of copying code into the python interpreter
" and executing it to see how my new code would act. to reduce the effort
" required by copy&paste, I decided to make vim more friendly for that style
" of development. this is the result. I apologize for the hackiness.
"
" when a .py file is opened (determined by filetype), a buffer is created
"
" python-output
" this contains the output of all the code you've executed.
" by default this is shown in a splitscreened window
"
" Usage:
" Move the cursor to a line or hilight some text (visual mode)
" and hit '!' to execute in the python interpreter. it's output will
" be displayed in 'python-output'
"
" ! -- execute current selected row
" Ctrl+@ -- display repr for symbol under character
" Ctrl+_ -- display help for symbol under character
"
" Installation:
" If in posix, copy to ~/.vim/plugin/
" If in windows, copy to $USERPROFILE/vimfiles/plugin/
"
" basic knowledge of window management is required to use effectively. here's
" a quickref:
"
"   <C-w>s -- horizontal split
"   <C-w>v -- vertical split
"   <C-w>o -- hide all other windows
"   <C-w>q -- close current window
"   <C-w>{h,l,j,k} -- move to the window left,right,down,up from current one
"
" Configuration (via globals):
" string g:incpy#Name           -- the name of the output buffer that gets created.
" string g:incpy#Program        -- name of subprogram (if empty, use vim's internal python)
" int    g:incpy#ProgramEcho    -- whether the program should echo all input
" int    g:incpy#ProgramFollow  -- go to the end of output when input is sent
" int    g:incpy#ProgramStrip   -- whether to strip leading indent
" string g:incpy#WindowPosition -- buffer position.  ['above', 'below', 'left', 'right']
" float  g:incpy#WindowRatio    -- window size on creation
" dict   g:incpy#WindowOptions  -- new window options
" int    g:incpy#WindowPreview  -- use preview windows
"
" Todo:
"       the auto-popup of the buffer based on the filetype was pretty cool
"       if some of the Program output is parsed, it might be possible to
"           create a fold labelled by the first rw python code that
"           exec'd it
"       maybe exeecution of the contents of a register would be useful
"       merge the main module with the python module so it's portable
"           and easy to install.
"       verify everything is cool in the linux-world

if has("python")

" vim string manipulation for indents and things
function! s:count_indent(string)
    " count the beginning whitespace of a string
    let characters = 0
    for c in split(a:string,'\zs')
        if stridx(" \t",c) == -1
            break
        endif
        let characters += 1
    endfor
    return characters
endfunction

function! s:find_common_indent(lines)
    " find the smallest indent
    let smallestindent = -1
    for l in a:lines
        " skip lines that are all whitespace
        if strlen(l) == 0 || l =~ '^\s\+$'
            continue
        endif

        let spaces = s:count_indent(l)
        if smallestindent < 0 || spaces < smallestindent
            let smallestindent = spaces
        endif
    endfor
    return smallestindent
endfunction

function! s:strip_indentation(lines)
    let indentsize = s:find_common_indent(a:lines)

    " remove the indent
    let results = []
    let prevlength = 0
    for l in a:lines
        if strlen(l) == 0
            let row = repeat(" ",prevlength)
        else
            let row = strpart(l,indentsize)
            let prevlength = s:count_indent(row)
        endif
        let results += [row]
    endfor
    return results
endfunction

function! s:selected() range
    " really, vim? really??
    let oldvalue = getreg("")
    normal gvy
    let result = getreg("")
    call setreg("", oldvalue)
    return result
endfunction

"" private window management
function! s:windowselect(id)
    " select the requested windowid, return the previous window id
    let current = winnr()
    execute printf("%d wincmd w", a:id)
    return current
endfunction

function! s:windowtail(bufid)
    " tail the window with the requested bufid
    let last = s:windowselect(bufwinnr(a:bufid))
    noautocmd normal gg
    noautocmd normal G
    call s:windowselect(last)
endfunction

function! s:currentWindowSize(pos)
    if a:pos == "left" || a:pos == "right"
        return winwidth(0)
    elseif a:pos == "above" || a:pos == "below"
        return winheight(0)
    else
        throw printf("Invalid position %s", a:pos)
    endif
endfunction

" internal conversions
function! s:positionToLocation(pos)
    if a:pos == "left" || a:pos == "above"
        return "leftabove"
    elseif a:pos == "right" || a:pos == "below"
        return "rightbelow"
    else
        throw printf("Invalid position %s", a:pos)
    endif
endfunction

function! s:positionToSplit(pos)
    if a:pos == "left" || a:pos == "right"
        return "vsplit"
    elseif a:pos == "above" || a:pos == "below"
        return "split"
    else
        throw printf("Invalid position %s", a:pos)
    endif
endfunction

function! s:optionsToCommandLine(options)
    if type(a:options) != type({})
        throw printf("Invalid options type %d", type(a:options))
    endif

    " parse options
    let result = []
    for k in keys(a:options)
        if type(a:options[k]) == type(0)
            call add(result, printf("%s=%d",k,a:options[k]))
        elseif type(a:options[k]) == type("")
            call add(result, printf("%s=%s",k,a:options[k]))
        else
            call add(result, printf("%s",k))
        endif
    endfor
    return join(result, "\\ ")
endfunction

function! s:windowcreate(bufid, pos, size, options)
    " open the buffer with id /bufid/  at the requested position with options.
    "   return the buffer-id
    let current = winnr()

    if g:incpy#WindowPreview > 0
        if type(a:options) == type({}) && len(a:options) > 0
            execute printf("noautocmd silent %s pedit! +setlocal\\ %s %s", s:positionToLocation(a:pos), s:optionsToCommandLine(a:options), bufname(a:bufid))
        else
            execute printf("noautocmd silent %s pedit! %s", s:positionToLocation(a:pos), bufname(a:bufid))
        endif
    else
        if type(a:options) == type({}) && len(a:options) > 0
            execute printf("noautocmd silent %s %d%s! +setlocal\\ %s %s", s:positionToLocation(a:pos), a:size, s:positionToSplit(a:pos), s:optionsToCommandLine(a:options), bufname(a:bufid))
        else
            execute printf("noautocmd silent %s %d%s! %s", s:positionToLocation(a:pos), a:size, s:positionToSplit(a:pos), bufname(a:bufid))
        endif
    endif
    call s:windowselect(current)
    return bufwinnr(bufnr(a:bufid))
endfunction

" bufnr(bufid) -- returns -1 if buffer doesn't exist
" winnr() -- number of current window
" bufwinnr(bufid) -- window for bufid
" winbufnr(winid) -- bufid for window

""" public window management
function! incpy#WindowCreate(bufid, position, ratio, options)
    if bufnr(a:bufid) == -1
        throw printf("Buffer %d does not exist", a:bufid)
    endif
    if type(a:ratio) != type(0.0) || a:ratio <= 0.0 || a:ratio >= 1.0
        throw printf("Invalid ratio type %d (%s)", type(a:ratio), string(a:ratio))
    endif

    let size = float2nr(floor(s:currentWindowSize(a:position) * a:ratio))
    let id = s:windowcreate(a:bufid, a:position, size, a:options)
    let current = s:windowselect(id)
        let b:lastwindowview = winsaveview()
        let b:lastwindowsize = winrestcmd()
    call s:windowselect(current)
endfunction

function! incpy#WindowShow(bufid, position)
    if bufnr(a:bufid) == -1
        throw printf("Buffer %d does not exist", a:bufid)
    endif
    if bufwinnr(a:bufid) != -1
        throw printf("Window for %d is already showing", a:bufid)
    endif

    let last = winnr()
        execute printf("noautocmd silent %s %s! %s", s:positionToLocation(a:position), s:positionToSplit(a:position), bufname(a:bufid))
        execute b:lastwindowsize
        call winrestview(b:lastwindowview)
    call s:windowselect(last)
endfunction

function! incpy#WindowHide(bufid)
    if bufnr(a:bufid) == -1
        throw printf("Buffer %d does not exist", a:bufid)
    endif
    if bufwinnr(a:bufid) == -1
        throw printf("Window for %d is already hidden", a:bufid)
    endif

    let last = s:windowselect(bufwinnr(a:bufid))
        let b:lastwindowview = winsaveview()
        let b:lastwindowsize = winrestcmd()
        if g:incpy#WindowPreview > 0
            noautocmd silent pclose!
        else
            noautocmd silent close!
        endif
    call s:windowselect(last)
endfunction

" incpy methods
function! incpy#SetupPython(currentscriptpath)
    python import sys,os,vim
    let m = substitute(a:currentscriptpath, "\\", "/", "g")

    " add the python path using the runtimepath directory that this script is contained in
    for p in split(&runtimepath,",")
        let p = substitute(p, "\\", "/", "g")
        if stridx(m, p, 0) == 0
            execute printf("python sys.path.append('%s/python')", p)
            return
        endif
    endfor

    " otherwise, look up from our current script's directory for a python sub-directory
    let p = finddir("python", m . ";")
    if isdirectory(p)
        execute printf("python sys.path.append('%s')", p)
        return
    endif

    throw printf("Unable to determine basepath from script %s",m)
endfunction

""" external interfaces
function! incpy#Execute(line)
    execute printf("python __incpy__().execute('%s')", escape(a:line, "'\\"))
    if g:incpy#ProgramFollow
        call s:windowtail(g:incpy#BufferId)
    endif
endfunction
function! incpy#Range(begin,end)
    let lines = getline(a:begin,a:end)
    if g:incpy#ProgramStrip
        let lines = s:strip_indentation(lines)

        " if last line starts with whitespace (indented), append a newline
        if len(lines) > 0 && lines[-1] =~ '^\s\+'
            let lines += [""]
        endif
    endif

    let code_s = join(map(lines, 'escape(v:val, "''\\")'), "\\n")
    execute printf("python __incpy__().execute('%s')", code_s)
    if g:incpy#ProgramFollow
        call s:windowtail(g:incpy#BufferId)
    endif
endfunction
function! incpy#Evaluate(expr)
    "execute printf("python __incpy__().execute('_=%s;print _')", escape(a:expr, "'\\"))
    "execute printf("python __incpy__().execute('sys.displayhook(%s)')", escape(a:expr, "'\\"))
    execute printf("python __incpy__().execute('__builtin__._=%s;print __builtin__._')", escape(a:expr, "'\\"))
    if g:incpy#ProgramFollow
        call s:windowtail(g:incpy#BufferId)
    endif
endfunction
function! incpy#Halp(expr)
    execute printf("python __incpy__().execute('__import__(\\'__builtin__\\').help(%s)')", escape(a:expr, "'\\"))
endfunction

" Create vim commands
function! incpy#MapCommands()
    command PyLine call incpy#Range(line("."),line("."))
    command PyBuffer call incpy#Range(0,line('$'))

    command -nargs=1 Py call incpy#Execute(<q-args>)
    command -range PyRange call incpy#Range(<line1>,<line2>)

    " python-specific commands
    command -nargs=1 PyEval call incpy#Evaluate(<q-args>)
    command -range PyEvalRange <line1>,<line2>call incpy#Evaluate(s:selected())
    command -nargs=1 PyHelp call incpy#Halp(<q-args>)
    command -range PyHelpRange <line1>,<line2>call incpy#Halp(s:selected())
endfunction

" Setup key mappings
function! incpy#MapKeys()
    nmap ! :PyLine<C-M>
    vmap ! :PyRange<C-M>

    " python-specific mappings
    nmap <C-@> :call incpy#Evaluate(expand("<cword>"))<C-M>
    vmap <C-@> :PyEvalRange<C-M>
    nmap  :call incpy#Halp(expand("<cword>"))<C-M>
    vmap <C-_> :PyHelpRange<C-M>
endfunction

" Setup default options
function! incpy#SetupOptions()
    let defopts = {
\        "Name" : "Scratch",
\        "Program" : "",
\        "ProgramEcho" : 1,
\        "ProgramFollow" : 1,
\        "ProgramStrip" : 1,
\        "WindowRatio" : 1.0/3,
\        "WindowPosition" : "below",
\        "WindowOptions" : {"buftype":"nowrite", "noswapfile":[], "updatecount":0, "nobuflisted":[], "filetype":"python"},
\        "WindowPreview" : 0,
\    }

    for o in keys(defopts)
        if ! exists("g:incpy#{o}")
            let g:incpy#{o} = defopts[o]
        endif
    endfor
endfunction

" Setup python interface
function! incpy#Setup()
    " Setup python interface

    python <<EOF
import sys,os,vim,__builtin__
def __incpy__():
    try:
        return __incpy__.cache
    except AttributeError:
        pass

    # save current stdin,stdout,stderr states
    state = sys.stdin,sys.stdout,sys.stderr
    gvars = vim.vars

    def log(data):
        _,out,_ = state
        out.write('incpy.vim : %s\n'% data)

    import incpy
    class __internal(__builtin__.object):
        def __init__(self):
            log('choosing internal python backend')
        def __del__(self):
            sys.stdin,sys.stdout,sys.stderr = self.state
        def write(self, data):
            return self.buffer.write(data)
        def start(self):
            log('redirecting sys.{stdin,stdout,stderr} to %s'% repr(self.buffer))
            _,sys.stdout,sys.stderr = None, self.buffer, self.buffer
        def stop(self):
            log('restoring sys.{stdin,stdout,stderr} to %s'% repr(state))
            sys.stdin,sys.stdout,sys.stderr = state
        def execute(self, command):
            if bool(gvars['incpy#ProgramEcho']):
                self.buffer.write('\n'.join('## %s'% x for x in command.split('\n')) + '\n')
            exec command in globals()

    class __external(__builtin__.object):
        program,instance = None,None
        def __init__(self):
            log('choosing external program backend')
        def write(self, data):
            return self.buffer.write(data)
        def start(self):
            log("connecting i/o from %s to %s"% (repr(self.program), repr(self.buffer)))
            self.instance = incpy.vimspawn(self.buffer, self.program)
        def stop(self):
            if not self.instance.running:
                log("refusing to stop already terminated process %s"% repr(self.instance))
                return
            log("killing process %s"% repr(self.instance))
            self.instance.stop()
            log('disconnecting std i/o from to %s'% repr(self.buffer))
        def execute(self, command):
            if bool(gvars['incpy#ProgramEcho']):
                self.buffer.write('%s\n'% command)
            return self.instance.write(command + "\n")

    def backend(program):
        if len(program) > 0:
            res = __external()
            res.program = program
            return res 
        return __internal()

    # determine which backend to choose
    cache = backend(gvars["incpy#Program"])

    # create buffer
    buf = incpy.buffer.new(gvars["incpy#Name"])
    gvars["incpy#BufferId"] = buf.number
    cache.buffer = buf

    # create window
    windowcreate = vim.Function('incpy#WindowCreate')
    windowcreate(buf.number, gvars["incpy#WindowPosition"], gvars["incpy#WindowRatio"], gvars["incpy#WindowOptions"])

    # start app
    cache.start()

    __incpy__.cache = cache
    return __incpy__()

EOF
endfunction

    let s:current_script=expand("<sfile>:p:h")
    call incpy#SetupOptions()
    call incpy#SetupPython(s:current_script)
    call incpy#Setup()
    call incpy#MapCommands()
    call incpy#MapKeys()

    autocmd VimEnter * python __incpy__()
    autocmd VimLeavePre * python __incpy__().stop()

else
    echoerr "Vim compiled without python support. Unable to initialize plugin from ". expand("<sfile>")
endif
