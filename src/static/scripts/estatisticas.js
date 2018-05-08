var ruleChart;

$(document).ready(function(){

    var today = new Date();
    var before =new Date(); 
    before.setDate(today.getDate() - 5);

    $('#data-inicio').datepicker();
    $('#data-fim').datepicker();

    $('#data-inicio').datepicker('setDate', before);
    $('#data-fim').datepicker('setDate', today);


    // ruleChart = new Chart($('#ruleChart'), {
    //     type : 'line',
    //     data : {
    //         datasets : [{
    //             data : [],
    //             label : 'Regras',
    //             borderColor : 'red',
    //             fill : true
    //         }]  
    //     },
    //     options: {
    //       title: {
    //         display: true,
    //         text: 'Regras geradas por dia'
    //       }
    //     }
    // });

    $('.datepicker').on('change', function(){
        var inicio = $('#data-inicio').val();
        var fim = $('#data-fim').val();

        if( inicio == null || inicio == "" || fim == null || fim == "")
            return ;
        
        // updateGraph(ruleChart, inicio, fim)

        $.ajax({
            url : '/estatisticas',
            data: {
                inicio : inicio,
                fim : fim
            }, 
            cache : false,
            dataType : 'json',
            method: 'post',
            success : function(data){
                
                var topIpsBody = $('#top-ips > tbody');

                topIpsBody.html('');
                $.each(data.top_ips, function(index, value){

                    var ip = value.source_ip.split('/')[0];

                    topIpsBody.append(
                        '<tr> '+
                        '   <td>'+ip+'</td>'+
                        '   <td>'+value.doc_count+'</td>'+
                        '</tr> '
                    );

                    if(index == 4)
                        return false;
                });

                var topPortsBody = $('#top-ports > tbody');

                topPortsBody.html('');
                var count = 0;
                $.each(data.top_ports, function(index, value){

                    if(value.destination_port.trim() != ""){
                        topPortsBody.append(
                            '<tr> '+
                            '   <td>'+value.destination_port+'</td>'+
                            '   <td>'+value.doc_count+'</td>'+
                            '</tr> '
                        );
                        count++;
                    }
                    if(count == 5)
                        return false;
                });
            }
        });
    });

    $('.datepicker').change();
});



function get_between(inicio, fim){
    data_inicio = to_date(inicio);
    data_fim = new to_date(fim);

    dates = [];
    while ( data_fim >= data_inicio ){
        dates.push(format_date(data_inicio));
        data_inicio.setDate(data_inicio.getDate() + 1);
    }
    return dates;
}

function get_n_lesser(n, raw_date){

    dates = [];
    date = to_date(raw_date);
    
    for(i=0; i<n; i++){
        date.setDate(date.getDate() - 1);
        dates.push(format_date(date));
    }
    return dates;
}

function get_n_greater(n, raw_date){
    dates = [];
    date = to_date(raw_date);
    
    for(i=0; i<n; i++){
        date.setDate(date.getDate() + 1);
        dates.push(format_date(date));
    }
    return dates;
}

function format_date(date){
    
    var day = date.getDate().toString();
    var month = (date.getMonth() + 1).toString();
    if( day.length != 2 )
        day = '0'+day;
    
    if( month.length != 2)
        month = '0'+month;

    return date.getFullYear()+'-'+month+'-'+day;
}

function to_date(raw_date){

    parts = raw_date.split('/')
    return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));
}


function updateGraph(chart, inicio, fim){
    var labels = []
    
    labels = labels.concat(get_n_lesser(2,inicio));
    labels = labels.concat(get_between(inicio, fim));
    labels = labels.concat(get_n_greater(2, fim));

    console.log(labels);

    $.ajax({
        url : '/grafico',
        data: {
            inicio : inicio,
            fim : fim
        }, 
        cache : false,
        dataType : 'json',
        method: 'post',
        success : function(rules){

            chart.data.labels.push(labels);
            $.each(labels, function(i, label){
                chart.data.datasets[0].data.push({
                    x : label,
                    y : label in rules ? rules[label] : 0
                })
            });
            chart.update();
        }
    });
}