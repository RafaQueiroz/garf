

function remove(line_number){

    var rule = document.getElementById('rules-table').rows[line_number].cells[0].innerHTML;
    document.getElementById('rule').value = rule;
    document.getElementById('remove-rule').submit();

}