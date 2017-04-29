$(document).ready(function() {
	// Set up web socket
	var urlParser = document.createElement("a");
	urlParser.href = window.location.href;
	var ws_ip = urlParser.hostname;
	var ws_port = %(ws_port)s;
	var ws = new WebSocket("ws://" + ws_ip + ":" + ws_port);

	ws.onopen = function() {
		console.log("Web socket connection established.");
	};

	ws.onmessage = function(e) {
		// console.log(e.data);
		var msg = JSON.parse(e.data);
		msg.forEach(function(m) {
			var key = m[0];
			var val = m[1];
			var $form = $("form[data-key='" + key + "']");

			// Create new redis key-value form
			if ($form.length == 0) {
				var form = "<form data-key='" + key + "'><div class='keyval-card'>\n";
				form += "\t<div class='key-header'>\n";
				form += "\t\t<label>" + key + "</label>\n";
				form += "\t\t<input type='submit' value='Set' title='Set values in Redis: <enter>'>\n";
				form += "\t\t<input type='button' value='Rep' class='repeat' title='Repeat value of first element: <shift-enter>'>\n";
				form += "\t\t<input type='button' value='Tog' class='toggle' title='Toggle values between current state and 0: <alt-enter>'>\n";
				form += "\t</div>\n";
				form += "\t<div class='val-body'>\n";
				if (typeof(val) === "string") {
					form += "\t\t<input class='val val-string' type='text' value='" + val + "'>\n";
				} else {
					val.forEach(function(el, idx) {
						if (idx %% 3 == 0) {
							form += "\t\t<div class='val-triplet'>\n";
						}
						form += "\t\t\t<input class='val' type='text' value='" + el + "'>\n";
						if (idx %% 3 == 2) {
							form += "\t\t</div>\n";
						}

					});
				}
				form += "\t</div>\n";
				form += "</div></form>\n";
				$("body").append(form);
				return;
			}

			// Update redis val as simple string
			var $inputs = $form.find("input.val");
			if (typeof(val) === "string" && val != "NaN") {
				for (var i = 1; i < $inputs.length; i++) {
					$inputs.eq(i).remove();
				}
				$inputs.eq(0).val(val);
				$inputs.addClass("val-string");
				return;
			}

			// Update redis val as array
			val.forEach(function(el, idx) {
				var $input = $inputs.eq(idx);
				$input.removeClass("val-string");

				// Extend array if necessary
				if ($input.length == 0) {
					if (idx %% 3 == 0) {
						var div = "<div class='val-triplet'>\n";
						div += "\t\t<input class='val' type='text' value='" + el + "'>\n";
						div += "</div>";
						$form.find("input.val").eq(idx - 1).parent().after(div);
						return;
					}
					var input = "\t\t<input class='val' type='text' value='" + el + "'>\n";
					$form.find("input.val").eq(idx - 1).after(input);
					return;
				}

				$input.val(el);
			});

			// Shorten array if necessary
			for (var i = val.length; i < $inputs.length; i++) {
				if (i %% 3 == 0) {
					$inputs.eq(i).parent().remove();
					continue;
				}
				$inputs.eq(i).remove();
			}
		});
	};

	var ajaxSendRedis = function(key, val) {
		// Send updated key-val pair via POST
		data = {};
		data[key] = JSON.stringify(val);
		console.log(data);
		$.ajax({
			method: "POST",
			url: "/",
			data: data
		});
	};

	$(document).on("click", "input.repeat", function(e) {
		e.preventDefault(e);

		var $form = $(this).closest("form");

		// Get key
		var key = $form.attr("data-key");

		// Get first value in array
		var $inputs = $form.find("input.val");
		var el = $inputs.eq(0).val();
		var num = parseFloat(el);
		if (isNaN(num) || el.search(" ") != -1) {
			console.log("Can't repeat a non-number");
			return;
		}

		// Create full array from num
		var val = [];
		for (var i = 0; i < $inputs.length; i++) {
			val.push(num.toString());
		}

		ajaxSendRedis(key, val);
	});

	$(document).on("click", "input.toggle", function(e) {
		e.preventDefault(e);

		var $form = $(this).closest("form");

		// Get key
		var key = $form.attr("data-key");

		// Get val
		var val;
		if (!$form.attr("data-val")) {
			// Collect input values into array
			var $inputs = $form.find("input.val");
			val = $inputs.map(function() {
				var el = $(this).val();
				var num = parseFloat(el);
				if (isNaN(num) || el.search(" ") != -1)
					return el;
				return num.toString();
			}).get();

			// If val is 0, set to 1
			var el;
			if (val == "0") {
				el = "1";
			} else {
				el = "0";
				$form.attr("data-val", JSON.stringify(val));
			}

			// Create full array from num
			val = [];
			for (var i = 0; i < $inputs.length; i++) {
				val.push(el);
			}
		} else {
			// Get stored val and restore it
			val = JSON.parse($form.attr("data-val"));
			$form.attr("data-val", "");
		}

		ajaxSendRedis(key, val);
	});

	$(document).on("keydown", "form", function(e) {
		// Click repeat button on <shift-enter>
		if (e.shiftKey && e.keyCode == 13) {
			e.preventDefault(e);
			$(this).find("input.repeat").click();
		}

		if (e.altKey && e.keyCode == 13) {
			e.preventDefault(e);
			$(this).find("input.toggle").click();
		}
	});

	// Change redis values on form submit
	$(document).on("submit", "form", function(e) {
		e.preventDefault(e);

		var key = $(this).attr("data-key");

		// Collect input values into array
		var val = $(this).find("input.val").map(function() {
			var el = $(this).val();
			var num = parseFloat(el);
			if (isNaN(num) || el.search(" ") != -1)
				return el;
			return num.toString();
		}).get();

		ajaxSendRedis(key, val);
	});
});

