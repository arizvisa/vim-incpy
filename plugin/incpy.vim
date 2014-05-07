" Incremental Python(?)
" siflus@gmail.com
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
" basic knowledge of window management is required to use this effectively
"
" Configuration:
" incpy uses 4 options that are set via global variables.
"
" string g:PyBufferName      - the name of the output buffer that gets created.
" string g:PyBufferPlacement - buffer position.  ['above', 'below']
" string g:PyBufferSize      - Buffer Size on Creation
" int g:PyEnableHide         - whether to enable support for autohiding
" int g:PyHideDelay          - the number of keys you'll have to hit before the
"                              python-output window AutoHides itself
" int g:PyNewline            - append this number of lines after each execution

if has("python")
    " initialize some private variables
    let g:_PyShowAlreadySized = 0
    let g:_PyHideDelayCount = 0
    let g:_PyHideSafe = 0
    let g:_PyShowSetSize = 0

    "" options
    let PyOptions = {}

    " python buffer
    let PyOptions['g:PyBufferName'] = 'python-output'
    let PyOptions['g:PyBufferPlacement'] = 'below'

    " autohide
    let PyOptions['g:PyEnableHide'] = 1
    let PyOptions['g:PyHideDelay'] = 10

    " newline
    let PyOptions['g:PyNewline'] = 1

    if exists('g:PyBufferSize')
        let g:_PyShowSetSize = 1
    endif

    if ! exists('g:PyDisable')
        let g:PyDisable = 1
    endif

    " set defaults in case they aren't set
    for k in keys(PyOptions)

        let v = PyOptions[k]

        if type(v) == 1
            let v = '"'. v .'"'
        endif

        if !exists(k)
            execute( "let ". k ."=". v )
        endif
    endfor

    python <<EOF

def __incpy__():
    '''
    this function is really a front to hide the interface for
    incremental python
    '''

    import os
    import vim

    ## internal defaults in case the vimscript doesn't specify these options
    PYOPTIONS = {
        'pyw-placement' : 'below',
        'debug' : False
    }

    try:
        # i'm a dick
        return __incpy__.cache
    except AttributeError:
        pass

    class pyb:
        '''
        represents a python buffer and provides an interface that makes it
        look like a write-only 'file' object
        '''
        id = 0  #our id

        def __init__(self, name):
            self.name = name
            self.create()

        def get(self):
            '''go through vim.buffers trying to find ourself'''
            def _m_file(x):
                if x.name:
                    return x.name.endswith(self.name)
            
            buf = filter( _m_file, vim.buffers )
            if not buf:
                return None

            return buf[0]

        def create(self):
            '''create our preview window'''
            vim.command('silent pedit %s'% self.name)
            self.buffer = self.get()
            self.id = self.buffer.number
            vim.command('silent pclose')

        def write(self, data):
            '''for writing'''

            # HACK: for some lame reason, vim writes a ['\n'] before any
            #       printed text. this keeps track of all data that's been
            #       passed to us and removes the first newline it encounters.
            #       this has the side effect of breaking output of a single
            #       '\n'. oh well.
            try:
                self.__last__
            except AttributeError:
                self.__last__ = []

#            self.buffer[-1:-1] = [repr(type(data)) + repr(data)]
            if data == '\n':
                if len(self.__last__) > 0:
                    self.__last__ = []
#                    self.buffer[-1:-1] = ['-'*7]
                    return
                
            if PYOPTIONS['debug']:
                data = ' '.join( map(lambda x: ('%02x'% ord(x)), data) )
                data = '(%s) %s'%(len(self.__last__), data)

            if len(self.__last__) > 0:
                self.buffer[-1:-1] = data.split('\n')
            self.__last__.append(data)

        def clear(self):
            '''reset our buffer'''
            self.buffer[:] = ['']

    class pyw(pyb):
        '''
        "attempts" to manage a window for keeping it splitscreen
        '''
        _size = None

        def __init__(self, name):
            pyb.__init__(self, name)
            current = vim.current.window

            self.show()
            self._switch( self._find(self.id) )
            vim.command('setlocal buftype=nofile')
            self.hide()

            self._switch( current )
            self._size = []

        def _find(self, num=None):
            '''find window by buffer id'''
            wins = filter( lambda x: x.buffer.number == num, vim.windows )
            if not wins:
                return None
            return wins[0]

        def _switch(self, window):
            '''try its best to navigate to the specified window'''
            count = len(vim.windows)
            current = vim.current.window

            # start at the top
            vim.command('%d wincmd k'% count)

            # stop downwards till we can find ourself
            for i in range(count):
                if vim.current.window == window:
                    break
                vim.command('wincmd j')

            if vim.current.window != window:
                raise ValueError('unable to find window holding bufffer %d'%window.buffer.id)

        def write(self, data):
            pyb.write(self, data)

            current = vim.current.window
            self._switch( self._find(self.id) )

            # HACK: switch to our window and set it as non-modified
            #       so when a user quits it won't ask us to save it
            vim.command('setlocal nomodified')

            # HACK: autoscroll to the very end of the file so that user can
            #       see the output of their python
            vim.command('normal gg')
            vim.command('normal G')

            self._switch(current)

        def _savesize(self):
            window = self._find(self.id)
            self._size.append( window.height )

        def _getsize(self):
            return self._size.pop()

        size = property( fget=_getsize )

        def show(self, placement=PYOPTIONS['pyw-placement'], height=None):
            '''split ourselves into view if we aren't already showing'''
            v = self._find(self.id)
            if v:
                return

            current = vim.current.window
            vim.command('silent %s pedit %s'% (placement, self.name))

            # set some options
            window = self._find(self.id)
            try:
                if self.size:
                    window.height = self.size
            except:
                pass

            if height:
                window.height = height

            self._switch(current)

        def hide(self):
            '''destroy our preview window'''
            vim.command('silent pclose')


    ## back to __incpy__()
    ## we're going to create a stash that "looks" like a dict, but has
    ## 2 extra properties
    class res(dict):
        pass

    res.pyw = pyw
    res.pyb = pyb

    # store it where it will be used
    __incpy__.cache = res()

    return __incpy__()  # yea, i'm really a dick
    
EOF

    """ initialize with all options
    function PyInit()
        "" buffer creation
        execute("python __incpy__()['PYOUT'] = __incpy__().pyw('". g:PyBufferName ."')")
        execute("python __import__('sys').stdout = __incpy__()['PYOUT']")

        "" autohide
        if g:PyEnableHide == 1
            autocmd FileType python call PyShow()
            autocmd CursorMoved * call PyHideCheck()
        endif

        execute "autocmd BufEnter ". g:PyBufferName ." call PyBufEnter()"
        execute "autocmd BufLeave ". g:PyBufferName ." call PyBufLeave()"
    endfunction

    """ Python Evaluation
    function PyRemoveIndent(lines)
        " find the smallest indent
        let indent = -1
        for l in a:lines

            " skip empty lines
            if len(l) == 0
                continue
            endif

            let spaces = 0
            for c in split(l, '\zs')
                if c != ' '
                    break
                endif
                let spaces += 1
            endfor

            if indent < 0 || spaces < indent
                let indent = spaces
            endif
        endfor

        " remove the indent
        let results = []
        for l in a:lines
            let l = strpart(l, indent)
            let results += [l]
        endfor

        return results
    endfunction

    " evaluate one line of python
    function PyEval(l)
        let s = PyRemoveIndent([a:l])

        call PyShow()
        execute("python __incpy__()['PYOUT'].write('##". escape(s[0], "'") ."')")
        execute("python ". s[0])

        let c = g:PyNewline
        while c > 0
            execute("python __incpy__()['PYOUT'].buffer[-1:-1] = ['\\n']")
            let c -= 1
        endwhile
    endfunction

    " evaluate multiple lines of python
    function PyRange(begin, end)
        let lines = PyRemoveIndent( getline(a:begin, a:end) )

        " all together now
        let code = map( lines, 'escape(v:val, "\\")' )
        let code_s = join( code, '\n' )

        " all together now
        let rem = map( lines, '"##" . v:val')
        let rem_s = join( rem, '\n' )

        call PyShow()

        execute("python __incpy__()['PYOUT'].write('". escape(rem_s, "'") ."')")
        execute("python exec('". escape(code_s, "'") ."')")

        let c = g:PyNewline
        while c > 0
            execute("python __incpy__()['PYOUT'].buffer[-1:-1] = ['\\n']")
            let c -= 1
        endwhile
    endfunction

    " display help for something in our output buffer
    function PyHelp(arg)
        execute("python help('". escape(a:arg, "'") ."')")
    endfunction

    """ python-output window display
    function PyShow()
        let g:_PyHideDelayCount = 0

        """ LOL: this is fucking horrible
        if g:_PyShowSetSize == 1
            let g:_PyShowSetSize = 0
            execute("python __incpy__()['PYOUT'].show(placement='". g:PyBufferPlacement ."', height=". g:PyBufferSize .")")
            return
        endif

        execute("python __incpy__()['PYOUT'].show(placement='". g:PyBufferPlacement ."')")
    endfunction

    function PyHide()
        execute("python __incpy__()['PYOUT'].hide()")
    endfunction

    "" Auto-Hiding code
    function PyHideIncDelayCount()
        if g:_PyHideSafe == 0
            let g:_PyHideDelayCount += 1
        endif
    endfunction

    function PyHideCheck()
        if g:_PyHideDelayCount < g:PyHideDelay
            call PyHideIncDelayCount()
            return 0
        endif

        let g:_PyHideDelayCount = 0
        call PyHide()
        return 1
    endfunction

    "" Hooks for entry/exit of our python-output buffer
    function PyBufEnter()
        let g:_PyHideSafe = 1    
    endfunction
    function PyBufLeave()
        let g:_PyHideSafe = 0
        let g:_PyHideDelayCount = 0
        execute("python __incpy__()['PYOUT']._savesize()")
    endfunction

    " produce some useful commands
    command -range PyRange call PyRange(<line1>, <line2>)
    command -nargs=1 Py call PyEval(<q-args>)
    command -nargs=1 PyHelp call PyHelp(<q-args>)
    command PyLine call PyRange( line("."), line(".") )
    command PyBuffer call PyRange( 0, line('$'))

    " default mode maps
    vmap ! :PyRange<C-M>
    nmap ! :PyLine<C-M>

    if g:PyDisable == 0
        call PyInit()
    endif
endif

