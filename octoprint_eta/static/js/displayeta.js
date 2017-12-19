$(function() {
    function ETAModel(parameters) {
        var self = this;
        self.ETA = ko.observable("-");
        self.onBeforeBinding = function() {
            var element = $("#state").find(".accordion-inner .progress");
            if (element.length) {
                var text = gettext("ETA");
                element.before(text + ": <strong id='ETA_string' data-bind=\"html: ETA\"></strong><br>");
            }
        };
        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "octoprint_eta") {
                return;
            }
            self.ETA(data.eta_string);
        };

    }

    OCTOPRINT_VIEWMODELS.push([
        ETAModel, 
        ["printerStateViewModel"],
        ["#navbar_plugin_octoprint_eta","#ETA_string"]
    ]);

});


