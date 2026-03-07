(function () {
    function parseRelationData() {
        var element = document.getElementById("relation-data");
        if (!element) {
            return [];
        }
        try {
            return JSON.parse(element.textContent || "[]");
        } catch (error) {
            return [];
        }
    }

    function getFieldCenter(container, fieldId) {
        var target = container.querySelector('[data-field-id="' + fieldId + '"]');
        if (!target) {
            return null;
        }
        var containerRect = container.getBoundingClientRect();
        var rect = target.getBoundingClientRect();
        return {
            x: rect.left - containerRect.left + container.scrollLeft + rect.width / 2,
            y: rect.top - containerRect.top + container.scrollTop + rect.height / 2
        };
    }

    function drawPath(svg, start, end) {
        var dx = Math.max(80, Math.abs(end.x - start.x) / 2);
        var d = [
            "M", start.x, start.y,
            "C", start.x + dx, start.y,
            end.x - dx, end.y,
            end.x, end.y
        ].join(" ");
        var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        svg.appendChild(path);
    }

    function renderRelations() {
        var canvas = document.getElementById("relation-canvas");
        var svg = document.getElementById("relation-svg");
        if (!canvas || !svg) {
            return;
        }
        svg.innerHTML = "";
        svg.setAttribute("viewBox", "0 0 " + canvas.scrollWidth + " " + canvas.scrollHeight);
        var relations = parseRelationData();
        relations.forEach(function (relation) {
            var start = getFieldCenter(canvas, relation.leftFieldId);
            var end = getFieldCenter(canvas, relation.rightFieldId);
            if (start && end) {
                drawPath(svg, start, end);
            }
        });
    }

    function initFieldSelection() {
        var buttons = document.querySelectorAll(".field-pin");
        if (!buttons.length) {
            return;
        }
        var leftId = document.getElementById("left-field-id");
        var rightId = document.getElementById("right-field-id");
        var leftLabel = document.getElementById("left-field-label");
        var rightLabel = document.getElementById("right-field-label");
        var selected = [];

        function updateUi() {
            buttons.forEach(function (button) {
                button.classList.remove("is-selected");
            });
            selected.forEach(function (button) {
                button.classList.add("is-selected");
            });
            leftId.value = selected[0] ? selected[0].dataset.fieldId : "";
            rightId.value = selected[1] ? selected[1].dataset.fieldId : "";
            leftLabel.value = selected[0] ? selected[0].dataset.label : "";
            rightLabel.value = selected[1] ? selected[1].dataset.label : "";
        }

        buttons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (selected.length === 2) {
                    selected = [];
                }
                var exists = selected.some(function (item) {
                    return item === button;
                });
                if (exists) {
                    selected = selected.filter(function (item) {
                        return item !== button;
                    });
                } else {
                    selected.push(button);
                }
                updateUi();
            });
        });
        updateUi();
    }

    window.addEventListener("load", function () {
        initFieldSelection();
        renderRelations();
        window.addEventListener("resize", renderRelations);
        var canvas = document.getElementById("relation-canvas");
        if (canvas) {
            canvas.addEventListener("scroll", renderRelations);
        }
    });
})();
