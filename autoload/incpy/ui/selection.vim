""" Utilities for dealing with visual-mode selection
function! incpy#ui#selection#current() range
    " really, vim? really??
    let oldvalue = getreg("")
    normal gvy
    let result = getreg("")
    call setreg("", oldvalue)
    return split(result, '\n')
endfunction

function! incpy#ui#selection#range() range
    let [l:left, l:right] = [getcharpos("'<"), getcharpos("'>")]
    let [l:lline, l:rline] = [l:left[1], l:right[1]]
    let [l:lchar, l:rchar] = [l:left[2], l:right[2]]

    if l:lline < l:rline
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = [l:lchar, l:rchar]
    elseif l:lline > l:rline
        let [l:minline, l:maxline] = [l:rline, l:lline]
        let [l:minchar, l:maxchar] = [l:rchar, l:lchar]
    else
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = sort([l:lchar, l:rchar], 'N')
    endif

    let lines = getline(l:minline, l:maxline)
    if len(lines) > 2
        let selection = [strcharpart(lines[0], l:minchar - 1)] + lines[+1 : -2] + [strcharpart(lines[-1], 0, l:maxchar)]
    elseif len(lines) > 1
        let selection = [strcharpart(lines[0], l:minchar - 1)] + [strcharpart(lines[-1], 0, l:maxchar)]
    else
        let selection = [strcharpart(lines[0], l:minchar - 1, 1 + l:maxchar - l:minchar)]
    endif
    return selection
endfunction

function! incpy#ui#selection#block() range
    let [l:left, l:right] = [getcharpos("'<"), getcharpos("'>")]
    let [l:lline, l:rline] = [l:left[1], l:right[1]]
    let [l:lchar, l:rchar] = [l:left[2], l:right[2]]

    if l:lline < l:rline
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = [l:lchar, l:rchar]
    elseif l:lline > l:rline
        let [l:minline, l:maxline] = [l:rline, l:lline]
        let [l:minchar, l:maxchar] = [l:rchar, l:lchar]
    else
        let [l:minline, l:maxline] = [l:lline, l:rline]
        let [l:minchar, l:maxchar] = sort([l:lchar, l:rchar], 'N')
    endif

    let lines = getline(l:minline, l:maxline)
    let selection = map(lines, 'strcharpart(v:val, l:minchar - 1, 1 + l:maxchar - l:minchar)')
    return selection
endfunction
