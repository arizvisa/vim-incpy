" Just a utility for generating a python expression that accesses a vim global variable
function! incpy#python#global_variable(name)
    let interface = [printf('__import__(%s)', incpy#string#quote_single(join([g:incpy#PackageName, 'interface'], '.'))), 'interface']
    let gvars = ['vim', 'gvars']
    return printf("%s[%s]", join(interface + gvars, '.'), incpy#string#quote_double(a:name))
endfunction

" convert from a vim native type to a string that can be interpreted by python
function! s:render_vim_atomic(object)
    let object_type = type(a:object)
    if object_type == v:t_number
        return printf('%d', a:object)
    elseif object_type == v:t_string
        return incpy#string#quote_single(a:object)
    elseif object_type is v:null
        return 'None'
    elseif object_type == v:t_float
        return printf('%f', a:object)
    elseif object_type == v:t_bool
        return a:object? 'True' : 'False'
    elseif object_type == v:t_blob
        let items = []
        for by in a:object
            let items += [printf("%#04x", by)]
        endfor
        return printf('bytearray([%s])', join(items, ','))
    else
        throw printf("Unable to render the specified type (%d): %s", object_type, a:object)
    endif
endfunction

" convert from a vim type (container or native) to a string that can be interpreted by python
function! incpy#python#render(object)
    let object_type = type(a:object)
    if object_type == v:t_list
        let items = map(a:object, 'incpy#python#render(v:val)')
        return printf('[%s]', join(items, ','))
    elseif object_type == v:t_dict
        let rendered = map(a:object, 'printf("%s:%s", incpy#python#render(v:key), incpy#python#render(v:val))')
        let items = map(keys(rendered), 'get(rendered, v:val)')
        return printf('{%s}', join(items, ','))
    else
        return s:render_vim_atomic(a:object)
    endif
endfunction

""" Utility functions for indentation, stripping, string processing, etc.

" Normalize each of the lines from the a:lines parameter so that their common
" indent is stripped, with their heading and trailing whitespace removed. This
" way the lines can be executed in a python interpreter as a single statement.
function! incpy#python#normalize(lines)
    let indentsize = incpy#string#find_common_indent(a:lines)
    let stripped = incpy#string#strip_common_indent(a:lines, indentsize)

    " trim any beginning lines that are meaningless
    let l:start = 0
    for l:index in range(len(stripped))
        let l:item = stripped[l:index]
        if strlen(l:item) > 0 && l:item !~ '^\s\+$'
            break
        endif
        let l:start += 1
    endfor

    " trim any ending lines that are meaningless
    let l:tail = 0
    for l:index in range(len(stripped))
        let l:tail += 1
        let l:item = stripped[-(1 + l:index)]
        if strlen(l:item) > 0 && l:item !~ '^\s\+$'
            break
        endif
    endfor

    " if the last line is indented, then we append another newline (python)
    let trimmed = split(trim(join(stripped[l:start : -l:tail], "\n"), " \t\n", 2), "\n")
    if len(trimmed) > 0 && trimmed[-1] =~ '^\s\+'
        let result = add(trimmed, '')
    else
        let result = trimmed
    endif
    return join(result, "\n") .. "\n"
endfunction

" Select the current python expression in a more-complicated-than-necessary way.
function! incpy#python#expression()
    let [cword, l:line, cpos] = [expand("<cexpr>"), getline(line('.')), col('.') - 1]

    " Patterns which are used to find pieces of the expression. We depend on the
    " iskeyword character set always placing us at the beginning of an identifier.
    let pattern_conversion = ['-', '+', '~']
    let pattern_group = ['()', '[]', '{}']

    "" The logic for trying to determine the quotes for a string is pretty screwy.
    let pattern_string = ['''', '"']

    " Start out by splitting up our pattern group into a list that can be used.
    let _pattern_begin_list = reduce(pattern_group, { items, pair -> items + [pair[0]] }, [])
    let _pattern_end_list = reduce(pattern_group, { items, pair -> items + [pair[1]] }, [])

    " Figure out where the beginning of the current expression is at.
    let rpos = strridx(l:line, cword, cpos)
    if rpos >= 0 && cpos - rpos < len(cword)
        let start = strridx(l:line, cword, cpos)
    else
        let start = stridx(l:line, cword, cpos)
    endif

    " If we're at the beginning of a string or a group, then trust what the user gave us.
    if index(_pattern_begin_list + pattern_string, l:line[cpos]) >= 0
        let start = cpos

    " Otherwise, use the current expression. But if there's a sign in front, then use it.
    else
        let start = (index(pattern_conversion, l:line[start - 1]) < 0)? start : start - 1
    endif

    " Find the ending (space, quote, terminal-grouping) from `start` and trim spaces for the result.
    let stop = match(l:line, printf('[[:space:]%s]', join(pattern_string + map(copy(pattern_group), 'printf("\\%s", v:val[1])'), '')), start)
    let result = trim(l:line[start : stop])

    " If the result is an empty string, then strip quotes and bail with what we fetched.
    let _pattern_string = join(pattern_string, '')
    if match(result, printf('^[%s]\+$', pattern_string)) >= 0
        return trim(result, _pattern_string)
    endif

    " Otherwise we need to scan for the beginning and ending to determine the quoting type.
    let prefix = (start > 0)? matchstr(l:line[: start - 1], printf('[%s]\+$', _pattern_string)) : ''
    let trailer = matchstr(result, printf('[%s]\+$', _pattern_string))

    " If we have a prefix then trust it first. For python if the length >= 3, and it's duplicated,
    " then we trim it. Otherwise we can just take the first quote type that we found and use that.
    if len(prefix)
        if len(prefix < 3) || match(prefix, printf("^[%s]\{3\}", prefix[0])) < 0
            let [lside, rside] = [prefix[0], prefix[0]]
        else
            let [lside, rside] = [prefix[:3], prefix[:3]]
        endif

        return join([lside, trim(result, _pattern_string), rside], '')

    " If we got a trailer without the prefix, then scan for its terminator and update the result.
    elseif len(trailer)
        let qindex = stridx(l:line, trailer, stop + 1)
        let result = (qindex < 0)? result : join([result, strpart(l:line, stop + 1, qindex)], '')
    endif

    " Otherwise we count everything... ignoring how they are nested because we're writing fucking vimscript.
    let counts = {}
    for pair in pattern_group
        let counts[pair[0]] = count(result, pair[0])
        let counts[pair[1]] = count(result, pair[1])
    endfor

    " If there aren't any begin-group characters, then we can just trim and return it.
    if reduce(_pattern_begin_list, { total, character -> total + counts[character] }, 0) == 0
        return trim(result, join(_pattern_end_list, ''))
    endif

    " Otherwise, we've hit the worst-case and we need to iterate through the result to
    " collect the order we close the expression with and map them to the right character.
    let [order, _pattern_group_table] = [[], {}]
    for pair in pattern_group | let _pattern_group_table[pair[0]] = pair[1] | endfor

    " Push them onto a stack instead of appending to a list in order to save a reverse.
    for character in result
        if index(_pattern_begin_list, character) >= 0
            let order = [_pattern_group_table[character]] + order
        endif
    endfor

    " Now we can trim and append the determined order to our result.
    let trimmed = trim(result, join(_pattern_end_list, ''), 2)
    return join([trimmed, join(order, '')], '')
endfunction
