function! s:keyword_under_cursor()
    let res = expand("<cexpr>")
    return len(res)? res : expand("<cword>")
endfunction

""" Mapping of vim commands and keys

" Create some vim commands that can interact with the plugin
function! incpy#bindings#commands()
    if has('folding')
        command PyLine call incpy#Range(foldclosed(line('.'))>0? foldclosed(line('.')) : line('.'), foldclosedend(line('.'))>0? foldclosedend(line('.')) : line('.'))
    else
        command PyLine call incpy#Range(line("."), line("."))
    endif
    command PyBuffer call incpy#Range(0, line('$'))
    command -range PyRange call incpy#Range(<line1>, <line2>)

    command -nargs=1 Py call incpy#Execute(<q-args>)
    command -nargs=1 PyRaw call incpy#ExecuteRaw(<q-args>)
    command -range PyExecuteRange <line1>,<line2>call incpy#ExecuteRange()
    command -range PyExecuteBlock <line1>,<line2>call incpy#ExecuteBlock()
    command -range PyExecuteSelection <line1>,<line2>call incpy#ExecuteSelected()

    command -nargs=1 PyEval call incpy#Evaluate(<q-args>)
    command -range PyEvalRange <line1>,<line2>call incpy#EvaluateRange()
    command -range PyEvalBlock <line1>,<line2>call incpy#EvaluateBlock()
    command -range PyEvalSelection <line1>,<line2>call incpy#EvaluateSelected()

    command -nargs=1 PyHelp call incpy#Halp(<q-args>)
    command -range PyHelpSelection <line1>,<line2>call incpy#HalpSelected()
endfunction

" Set up the default key mappings for vim to use the plugin
function! incpy#bindings#setup()

    " Execute a single or range of lines
    nnoremap ! :PyLine<C-M>
    vnoremap ! :PyRange<C-M>

    " Python visual and normal mode mappings
    nnoremap <C-/> :call incpy#Evaluate(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-/> :PyEvalRange<C-M>

    nnoremap <C-\> :call incpy#Evaluate(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-\> :PyEvalRange<C-M>

    " Normal and visual mode mappings for windows
    nnoremap <C-@> :call incpy#Halp(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-@> :PyHelpSelection<C-M>

    " Normal and visual mode mappings for everything else
    nnoremap <C-S-@> :call incpy#Halp(<SID>keyword_under_cursor())<C-M>
    vnoremap <C-S-@> :PyHelpSelection<C-M>

    " If we have terminal support, then add a mapping that makes
    " pasting from a register similar to cmdline-mode.
    if has('terminal')
        tnoremap <silent> <C-R> <C-W>"

    elseif has('nvim')
        "tnoremap <expr> <C-R> '<C-\><C-o>"'.nr2char(getchar()).'p'
        tnoremap <silent> <C-R>= <Cmd>call chansend(b:terminal_job_id, eval(input('=')))<CR>
        tnoremap <silent> <C-R> <Cmd>call chansend(b:terminal_job_id, getreg(nr2char(getchar())))<CR>
    endif
endfunction
