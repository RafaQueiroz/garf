var ruleChart;

$(document).ready(function(){

    var today = new Date();
    var before =new Date(); 
    before.setDate(today.getDate() - 5);

    $('#data-inicio').datepicker();
    $('#data-fim').datepicker();

    $('#data-inicio').datepicker('setDate', before);
    $('#data-fim').datepicker('setDate', today);

    $('.datepicker').on('change', function(){
        var inicio = $('#data-inicio').val();
        var fim = $('#data-fim').val();

        if( inicio == null || inicio == "" || fim == null || fim == "")
            return ;
        
        $.ajax({
            url : '/historico',
            data: {
                inicio : inicio,
                fim : fim
            }, 
            cache : false,
            dataType : 'json',
            method: 'post',
            success : function(rules){
                
                var linhas = $('#historico > tbody ');

                linhas.html('');
                $.each(rules, function(index, value){
                    linhas.append(row(value));
                });
            }
        });
    });

    $('.datepicker').change();
});

function row(rule){


    var str_rule = 'iptables -A INPUT ';
    
    if(rule.protocol != undefined && rule.protocol != undefined)
        str_rule += '-p '+rule.protocol;

    if(rule.destination_port != undefined && rule.destination_port != "") 
        str_rule += ' --dport ' + rule.destination_port;

    str_rule += ' -s '+ rule.source_ip +' -j DROP';
    
    return ''+
        '<tr> ' +
        '   <td>'+str_rule+'</td>' +
        '   <td>'+rule.created_in+'</td>' +
        '</tr> ';
}