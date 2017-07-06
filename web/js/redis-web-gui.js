/**
 * redis-web-gui.js
 *
 * Author: Toki Migimatsu
 * Created: April 2017
 */

function htmlForm(key, val) {
	var form = "<a name='" + key + "'></a><form data-key='" + key + "'><div class='keyval-card'>\n";
	form += "\t<div class='key-header'>\n";
	form += "\t\t<label>" + key + "</label>\n";
	form += "\t\t<div class='buttons'>\n";
	form += "\t\t\t<input type='button' value='Cpy' class='copy' title='Copy value to clipboard'>\n";
	form += "\t\t\t<input type='button' value='Tog' class='toggle' title='Toggle values between current state and 0: <alt-enter>'>\n";
	form += "\t\t\t<input type='button' value='Rep' class='repeat' title='Repeat value of first element: <shift-enter>'>\n";
	form += "\t\t\t<input type='submit' value='Set' title='Set values in Redis: <enter>'>\n";
	form += "\t\t</div>\n";
	form += "\t</div>\n";
	form += "\t<div class='val-body'>\n";
	if (typeof(val) === "string") {
		form += "\t\t<div class='val-row'>\n";
		form += "\t\t\t<div class='val-string'>\n";
		form += "\t\t\t\t<input class='val' type='text' value='" + val + "'>\n";
		form += "\t\t\t</div>\n";
		form += "\t\t</div>\n";
	} else { // val should be a 2D array
		val.forEach(function(row, idx_row) {
			form += "\t\t<div class='val-row'>\n";
			row.forEach(function(el, idx) {
				if (idx %% 3 == 0) {
					form += "\t\t\t<div class='val-triplet'>\n";
				}
				form += "\t\t\t\t<input class='val' type='text' value='" + el + "'>\n";
				if (idx %% 3 == 2 || idx == row.length - 1) {
					form += "\t\t\t</div>\n";
				}
			});
			form += "\t\t</div>\n";
		});
	}
	form += "\t</div>\n";
	form += "</div></form>\n";
	return form;
}

function updateHtmlValues($form, val) {
	var $inputs = $form.find("input.class");
	var i = 0;
	val.forEach(function(row) {
		row.forEach(function(el) {
			$inputs.eq(i).val(el);
			i++;
		});
	});
}

function getMatrix($form) {
	return $form.find("div.val-row").map(function() {
		return [$(this).find("input.val").map(function() {
			return $(this).val();
		}).get().filter(function(el) {
			return el != "";
		})];
	}).get();
}

function fillMatrix(matrix, num) {
	matrix.forEach(function(row) {
		row.forEach(function(el, idx) {
			row[idx] = num.toString();
		});
	});
}

function matrixToString(matrix) {
	return matrix.map(function(row) {
		return row.join(" ");
	}).join("; ");
}

function matrixDim(val) {
	if (typeof(val) === "string") return "";
	return [val.length, val[0].length].toString();
}

// Send updated key-val pair via POST
function ajaxSendRedis(key, val) {
	data = {};
	data[key] = JSON.stringify(val);
	console.log(data);
	$.ajax({
		method: "POST",
		url: "/",
		data: data
	});
}

function toggleSidebar() {
	var container = $("#container").get(0);
	$("#left-col").show();
	if (container.clientWidth < $("#right-col").get(0).scrollWidth + $("#left-col").width()) {
		$("#left-col").hide();
	}
}

$(document).ready(function() {
	// Set up web socket
	var url_parser = document.createElement("a");
	url_parser.href = window.location.href;
	var ws_ip = url_parser.hostname;
	var ws_port = %(ws_port)s;
	var ws = new WebSocket("ws://" + ws_ip + ":" + ws_port);

	ws.onopen = function() {
		console.log("Web socket connection established.");
	};

	var matrix_dims = {};
	ws.onmessage = function(e) {
		// console.log(e.data);
		var msg = JSON.parse(e.data);
		msg.forEach(function(m) {
			// console.log(m);
			var key = m[0];
			var val = m[1];
			var $form = $("form[data-key='" + key + "']");

			// Create new redis key-value form
			if ($form.length == 0) {
				// Store size of matrix value
				matrix_dims[key] = matrixDim(val);

				var form = htmlForm(key, val);
				var $form = $(form).hide();
				var li = "<a href='#" + key + "' title='" + key + "'><li>" + key + "</li></a>";
				var $li = $(li).hide();

				// Find alphabetical ordering
				var keys = $("form").map(function() {
					return $(this).attr("data-key");
				}).get();
				var idx_key;
				for (idx_key = 0; idx_key < keys.length; idx_key++) {
					if (key < keys[idx_key]) break;
				}
				if (idx_key < keys.length) {
					$("form").eq(idx_key).before($form);
					$("#left-col a").eq(idx_key).before($li);
				} else {
					$("#keyval-card-container").append($form);
					$("#left-col ul").append($li)
				}
				$form.slideDown("normal");
				$li.slideDown("normal");
				return;
			}

			var matrix_dim = matrixDim(val);
			if (matrix_dim != matrix_dims[key]) {
				// Recreate html for resized matrix
				matrix_dims[key] = matrix_dim;

				// Store focus
				var $inputs = $form.find("input.val");
				var idx_input = -1;
				for (var i = 0; i < $inputs.length; i++) {
					if ($inputs.eq(i).is(":focus")) {
						idx_input = i;
						break;
					}
				}

				// Replace html
				$form.html(htmlForm(key, val));

				// Restore focus
				if (idx_input >= 0) {
					var $input = $form.find("input.val").eq(idx_input);
					var val_input = $input.val();
					$input.focus().val("").val(val_input);
				}
				return;
			}

			// Update html
			updateHtmlValues($form, val);
		});

		toggleSidebar();
	};

	// Send redis values on form submit
	$(document).on("submit", "form", function(e) {
		e.preventDefault();

		// Get keyval
		var $form = $(this);
		var key = $form.attr("data-key");
		var val = getMatrix($form);

		ajaxSendRedis(key, val);
	});

	// Repeat value of first element
	$(document).on("click", "input.repeat", function(e) {
		e.preventDefault();

		// Get keyval
		var $form = $(this).closest("form");
		var key = $form.attr("data-key");
		var val = getMatrix($form);

		// Fill array with num
		fillMatrix(val, val[0][0]);

		ajaxSendRedis(key, val);
	});

	// Toggle values between current state and 0
	$(document).on("click", "input.toggle", function(e) {
		e.preventDefault();

		// Get key
		var $form = $(this).closest("form");
		var key = $form.attr("data-key");

		// Get val
		var val;
		if (!$form.attr("data-val")) {
			// Store current matrix in form attribute
			val = getMatrix($form);
			$form.attr("data-val", JSON.stringify(val));

			// Fill array with 0
			fillMatrix(val, 0);
		} else {
			// Get stored val and restore it
			val = JSON.parse($form.attr("data-val"));
			$form.attr("data-val", "");
		}

		ajaxSendRedis(key, val);
	});

	// Copy values to clipboard
	$(document).on("click", "input.copy", function(e) {
		e.preventDefault();

		// Get val
		var $form = $(this).closest("form");
		var val = matrixToString(getMatrix($form));

		// Create temporary input to copy to clipboard
		var $temp = $("<input>");
		$("body").append($temp);
		$temp.val(val).select();
		document.execCommand("copy");
		$temp.remove();
	});

	// Form submission shortcuts
	$(document).on("keydown", "form", function(e) {
		// Click repeat button on <shift-enter>
		if (e.shiftKey && e.keyCode == 13) {
			e.preventDefault();
			$(this).find("input.repeat").click();
			return;
		}

		// Click toggle button on <alt-enter>
		if (e.altKey && e.keyCode == 13) {
			e.preventDefault();
			$(this).find("input.toggle").click();
			return;
		}
	});

	// Easy <tab> key jumping
	var processingAnimation = false;
	$(document).on("keydown", "input.val", function(e) {
		if (processingAnimation) {
			e.preventDefault();
			return;
		}

		// Select first input of next form if currently in last input of current form
		var $this = $(this);
		if (!e.shiftKey && e.keyCode == 9 && $this.is(":last-child")
		    && $this.parent().is(":last-child") && $this.parent().parent().is(":last-child"))
		{
			e.preventDefault();
			var $nextForm = $this.closest("form").nextAll("form:first");
			if ($nextForm.length == 0) return;

			// Scroll to next form if out of view
			var nextFormBottomRel = $nextForm.offset().top + $nextForm.height() + parseInt($nextForm.css("margin-bottom"));
			var nextFormBottomAbs = nextFormBottomRel + $("#right-col").scrollTop();
			if (nextFormBottomRel > window.innerHeight) {
				processingAnimation = true;
				$("#right-col").animate({scrollTop: nextFormBottomAbs - window.innerHeight}, 200, function() {
					$nextForm.find("input.val:first").focus();
					processingAnimation = false;
				});
				return;
			}
			$nextForm.find("input.val:first").focus();
		}

		// Select last input of previous form if currently in first input of current form
		if (e.shiftKey && e.keyCode == 9 && $this.is(":first-child")
			&& $this.parent().is(":first-child") && $this.parent().parent().is(":first-child")) {
			e.preventDefault();
			var $prevForm = $this.closest("form").prevAll("form:first");
			if ($prevForm.length == 0) return;

			// Scroll to previous form if out of view
			var prevFormTopRel = $prevForm.position().top;
			var prevFormTopAbs = prevFormTopRel + $("#right-col").scrollTop();
			if (prevFormTopRel < 0) {
				processingAnimation = true;
				$("#right-col").animate({scrollTop: prevFormTopAbs}, 200, function() {
					$prevForm.find("input.val:last").focus();
					processingAnimation = false;
				});
				return;
			}
			$prevForm.find("input.val:last").focus();
		}
	});

	// Focus on card selected in key list
	$(document).on("click", "a", function(e) {
		var key = this.hash.substr(1);
		var $form = $("form[data-key='" + key + "']");
		if ($form.length == 0) return;

		e.preventDefault();

		// Calculate relevant dimensions
		var $input = $form.find("input.val").eq(0);
		var windowMiddle = Math.floor(window.innerHeight / 2);
		var totalHeight = $("#right-col").get(0).scrollHeight;
		var formMiddleRel = $form.offset().top + Math.floor($form.height() / 2);
		var formMiddleAbs = formMiddleRel + $("#right-col").scrollTop();
		var isTop = formMiddleAbs < windowMiddle;
		var isBottom = totalHeight - formMiddleAbs < windowMiddle;

		var scrollTo = -1;
		if (isTop && formMiddleRel < formMiddleAbs) {
			// For top region, scroll to top if not scrolled up as far as possible
			scrollTo = 0;
		} else if (isBottom && window.innerHeight - formMiddleRel < totalHeight - formMiddleAbs) {
			// For bottom region, scroll to bottom if not scrolled down as far as possible
			scrollTo = totalHeight - window.innerHeight;
		} else if (!isTop && !isBottom && formMiddleRel != windowMiddle) {
			// For middle region, scroll desired card to middle of window
			scrollTo = formMiddleAbs - windowMiddle;
		}
		if (scrollTo >= 0) {
			$('#right-col').animate({scrollTop: scrollTo}, 200, function() {
				$input.focus();
			});
			return;
		}
		$input.focus();
	});

	// Hide sidebar when window is too small
	$(window).resize(toggleSidebar);
});

