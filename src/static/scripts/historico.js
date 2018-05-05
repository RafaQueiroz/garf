$(document).ready(function(){

    $('#data-inicio').datepicker();
    $('#data-fim').datepicker();


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
        })
    });

});

function row(rule){
    return ''+
        '<tr> ' +
        '   <td>iptables -A INPUT -p '+rule.protocol+' --dport ' + rule.destination_port + ' -s '+ rule.source_ip +' -j DROP </td>' +
        '   <td>'+rule.created_in+'</td>' +
        '</tr> ';
}