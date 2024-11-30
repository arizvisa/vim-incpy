""" Utilities for escaping strings and such
function! incpy#string#escape_single(string)
    return escape(a:string, '''\')
endfunction

function! incpy#string#escape_double(string)
    return escape(a:string, '"\')
endfunction

function! incpy#string#quote_single(string)
    return printf("'%s'", escape(a:string, '''\'))
endfunction

function! incpy#string#quote_double(string)
    return printf("\"%s\"", escape(a:string, '"\'))
endfunction

" escape the multiline string with the specified characters and return it as a single-line string
function! incpy#string#singleline(string, escape)
    let escaped = escape(a:string, a:escape)
    let result = substitute(escaped, "\n", "\\\\n", "g")
    return result
endfunction

""" Utilities for stripping strings and lists of strings.
function! s:striplist_by_option(option, lines)
    let items = a:lines

    " Strip the fetched lines if the user configured us to
    if type(a:option) == v:t_bool
        let result = a:option == v:true? map(items, "trim(v:val)") : items

    " If the type is a string, then use it as a regex that
    elseif type(a:option) == v:t_string
        let result = map(items, a:option)

    " Otherwise it's a function to use as a transformation
    elseif type(a:option) == v:t_func
        let F = a:option
        let result = F(items)

    " Anything else is an unsupported filtering option.
    else
        throw printf("Unable to strip lines using an unknown filtering option (%s): %s", typename(a:option), a:option)
    endif

    return result
endfunction

function! s:stripstring_by_option(option, string)
    if type(a:option) == v:t_bool
        let result = a:option == v:true? trim(a:string) : a:string

    elseif type(a:option) == v:t_string
        let expression = a:option
        let results = map([a:string], expression)
        let result = results[0]

    elseif type(a:option) == v:t_func
        let F = a:option
        let result = F([a:string])

    else
        throw printf("Unable to strip string due to an unknown filtering option (%s): %s", typename(a:option), a:option)
    endif
    return result
endfunction

function! incpy#string#strip(option, input)
    if type(a:input) == v:t_list
        let result = s:striplist_by_option(a:option, a:input)
    elseif type(a:input) == v:t_string
        let result = s:stripstring_by_option(a:option, a:input)
    else
        throw printf("Unknown parameter type: %s", type(a:input))
    endif
    return result
endfunction