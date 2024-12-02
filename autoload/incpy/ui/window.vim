""" Utilities for window management
function! incpy#ui#window#select(id)

    " check if we were given a bunk window id
    if a:id == -1
        throw printf("Invalid window identifier %d", a:id)
    endif

    " select the requested window id, return the previous window id
    let current = winnr()
    execute printf("%d wincmd w", a:id)
    return current
endfunction

function! incpy#ui#window#tail(bufid)

    " if we were given a bunk buffer id, then we need to bitch
    " because we can't select it or anything
    if a:bufid == -1
        throw printf("Invalid buffer identifier %d", a:bufid)
    endif

    " tail the window that's using the specified buffer id
    let last = incpy#ui#window#select(bufwinnr(a:bufid))
    if winnr() == bufwinnr(a:bufid)
        keepjumps noautocmd normal gg
        keepjumps noautocmd normal G
        call incpy#ui#window#select(last)

    " check which tabs the buffer is in
    else
        call incpy#ui#window#select(last)

        let tc = tabpagenr()
        for tn in range(tabpagenr('$'))
            if index(tabpagebuflist(1 + tn), a:bufid) > -1
                execute printf("tabnext %d", tn)
                let tl = incpy#ui#window#select(bufwinnr(a:bufid))
                keepjumps noautocmd normal gg
                keepjumps noautocmd normal G
                call incpy#ui#window#select(tl)
            endif
        endfor
        execute printf("tabnext %d", tc)
    endif
endfunction
