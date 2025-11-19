'use strict';

$(document).ready(function () {
    var data = [];
    var queryCnt = 100;

    function getData() {
        if (data.length > 0)
            data = data.slice(1);
        
        $.ajax({
            url: "/sensor/getTemp/" + queryCnt,
            type: "GET",
            dataType: "json",
            success: (res) => {
              data = res;
              
            },
            error: (error) => {
              console.log(error);
            }
          });

        // zip the generated y values with the x values
        var res = [];
        for (var i = 0; i < data.length; ++i){
            res.push([i, data[i]['value']])
            // res.push([new Date(data[i]['reg_date']), data[i]['value']]);
        }
        return res;
    }
    var options = {
        colors: ["#4fb7fe"],
        series: {
            shadowSize: 0,
            lines: {
                show: true,
                fill: true,
                fillColor: {
                    colors: [{
                        opacity: 0.5
                    }, {
                        opacity: 0.5
                    }]
                }
            }
        },
        yaxis: {
            min: 0,
            max: 110
        },
        xaxis: {
            show: false,
            min: 0,
            max: queryCnt
        },
        points: {
            show: true
        },
        grid: {
            backgroundColor: '#fff',
            borderWidth: 1,
            borderColor: '#fff',
            hoverable: true
        }

    };
    // up control widget
    var updateInterval = 50;
    var plot = $.plot($("#realtime"), [getData()], options);

    function update() {
        plot.setData([getData()]);
        // since the axes don't change, we don't need to call plot.setupGrid()
        plot.draw();
        setTimeout(update, updateInterval);
    }
    update();
});