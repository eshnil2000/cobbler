var js_growl = new jsGrowl('js_growl');

function get_latest_task_info(last) {

    /* FIXME: only show tasks since the last time interval */

    $.getJSON("/cblr/svc/op/tasks/since" + last,
        function(data){
          $.each(data, function(i,record){
               var id = record[0];
               var ts = record[1];
               var name = record[2];
               var state = record[3];
               var buf = "Task " + state + " : " + name + " <A HREF=\"/cobbler_web/tasklog/" + id + "\">(log)</A>";
               js_growl.addMessage({msg:buf});
          });
        });


}

function go_go_gadget() {
    js_growl.addMessage({msg:'Hello'})
    now = new Date()
    nowt = now.getTime()
    js_growl.addMessage({msg:nowt})
    get_latest_task_info(3)
}


