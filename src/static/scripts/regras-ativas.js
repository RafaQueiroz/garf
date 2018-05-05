

function remove(rule){
    $.ajax({
        url : '/remove-rule',
        data: {
            rule : JSON.stringify(rule)
        }, 
        cache : false,
        type: 'post',
        success : function(rules){
            location.reload();
        }
    });
}

