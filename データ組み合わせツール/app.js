(function () {
    var previewRelation = null;
    var currentSelection = [];
    var pendingRelations = [];

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

    function drawPath(svg, start, end, cssClassName) {
        var dx = Math.max(80, Math.abs(end.x - start.x) / 2);
        var d = [
            "M", start.x, start.y,
            "C", start.x + dx, start.y,
            end.x - dx, end.y,
            end.x, end.y
        ].join(" ");
        var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d);
        if (cssClassName) {
            path.setAttribute("class", cssClassName);
        }
        svg.appendChild(path);
    }

    function renderRelations() {
        var canvas = document.getElementById("relation-canvas");
        var svg = document.getElementById("relation-svg");
        if (!canvas || !svg) {
            return;
        }
        var width = Math.max(canvas.clientWidth, canvas.scrollWidth);
        var height = Math.max(canvas.clientHeight, canvas.scrollHeight);
        svg.innerHTML = "";
        svg.style.width = width + "px";
        svg.style.height = height + "px";
        svg.setAttribute("width", width);
        svg.setAttribute("height", height);
        svg.setAttribute("viewBox", "0 0 " + width + " " + height);
        var relations = parseRelationData();
        relations.forEach(function (relation) {
            var start = getFieldCenter(canvas, relation.leftFieldId);
            var end = getFieldCenter(canvas, relation.rightFieldId);
            if (start && end) {
                drawPath(svg, start, end, "");
            }
        });
        pendingRelations.forEach(function (relation) {
            var start = getFieldCenter(canvas, relation.leftFieldId);
            var end = getFieldCenter(canvas, relation.rightFieldId);
            if (start && end) {
                drawPath(svg, start, end, "pending");
            }
        });
        if (previewRelation && previewRelation.start && previewRelation.end) {
            drawPath(svg, previewRelation.start, previewRelation.end, "preview");
        }
    }

    function applySelection(selected) {
        currentSelection = selected.slice(0, 2);
        var buttons = document.querySelectorAll(".field-pin");
        var leftId = document.getElementById("left-field-id");
        var rightId = document.getElementById("right-field-id");
        var leftLabel = document.getElementById("left-field-label");
        var rightLabel = document.getElementById("right-field-label");
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

    function syncPendingRelationsInput() {
        var input = document.getElementById("pending-relations");
        if (input) {
            input.value = JSON.stringify(pendingRelations);
        }
    }

    function renderPendingRelations() {
        var list = document.getElementById("pending-relations-list");
        var empty = document.getElementById("pending-relations-empty");
        if (!list || !empty) {
            return;
        }
        list.innerHTML = "";
        if (!pendingRelations.length) {
            empty.style.display = "block";
            syncPendingRelationsInput();
            renderRelations();
            return;
        }
        empty.style.display = "none";
        pendingRelations.forEach(function (relation, index) {
            var item = document.createElement("div");
            item.className = "pending-item";
            var text = document.createElement("div");
            text.className = "pending-item-text";
            text.textContent = relation.leftLabel + " → " + relation.rightLabel;
            var button = document.createElement("button");
            button.type = "button";
            button.className = "btn danger";
            button.textContent = "削除";
            button.addEventListener("click", function () {
                pendingRelations.splice(index, 1);
                renderPendingRelations();
            });
            item.appendChild(text);
            item.appendChild(button);
            list.appendChild(item);
        });
        syncPendingRelationsInput();
        renderRelations();
    }

    function addPendingRelation(leftButton, rightButton) {
        if (!leftButton || !rightButton) {
            return false;
        }
        if (leftButton.dataset.datasetId === rightButton.dataset.datasetId) {
            return false;
        }
        var leftFieldId = String(leftButton.dataset.fieldId);
        var rightFieldId = String(rightButton.dataset.fieldId);
        var exists = pendingRelations.some(function (relation) {
            return relation.leftFieldId === leftFieldId && relation.rightFieldId === rightFieldId;
        });
        if (exists) {
            return false;
        }
        pendingRelations.push({
            leftFieldId: leftFieldId,
            rightFieldId: rightFieldId,
            leftLabel: leftButton.dataset.label,
            rightLabel: rightButton.dataset.label
        });
        renderPendingRelations();
        return true;
    }

    function initFieldSelection() {
        var buttons = document.querySelectorAll(".field-pin");
        if (!buttons.length) {
            return;
        }
        var selected = [];

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
                applySelection(selected);
            });
        });
        applySelection(selected);

        var stageButton = document.getElementById("stage-relation-btn");
        if (stageButton) {
            stageButton.addEventListener("click", function () {
                if (currentSelection.length !== 2) {
                    return;
                }
                if (addPendingRelation(currentSelection[0], currentSelection[1])) {
                    applySelection([]);
                    selected = [];
                }
            });
        }

        var clearButton = document.getElementById("clear-pending-btn");
        if (clearButton) {
            clearButton.addEventListener("click", function () {
                pendingRelations = [];
                renderPendingRelations();
            });
        }

        var relationForm = document.getElementById("relation-form");
        if (relationForm) {
            relationForm.addEventListener("submit", function () {
                syncPendingRelationsInput();
            });
        }

        renderPendingRelations();
    }

    function getCanvasStorageKey(canvas) {
        return "data-link-tool-node-positions:" + window.location.pathname;
    }

    function saveNodePositions(canvas) {
        var nodes = canvas.querySelectorAll(".node");
        var positions = {};
        nodes.forEach(function (node) {
            positions[node.dataset.datasetId] = {
                left: node.style.left,
                top: node.style.top
            };
        });
        try {
            window.localStorage.setItem(getCanvasStorageKey(canvas), JSON.stringify(positions));
        } catch (error) {
        }
    }

    function loadNodePositions(canvas) {
        var raw = "";
        try {
            raw = window.localStorage.getItem(getCanvasStorageKey(canvas)) || "";
        } catch (error) {
            raw = "";
        }
        var positions = {};
        if (raw) {
            try {
                positions = JSON.parse(raw) || {};
            } catch (error) {
                positions = {};
            }
        }
        var nodes = canvas.querySelectorAll(".node");
        nodes.forEach(function (node) {
            var saved = positions[node.dataset.datasetId];
            node.style.left = saved && saved.left ? saved.left : node.dataset.defaultLeft + "px";
            node.style.top = saved && saved.top ? saved.top : node.dataset.defaultTop + "px";
        });
    }

    function initNodeDragging() {
        var canvas = document.getElementById("relation-canvas");
        if (!canvas) {
            return;
        }
        loadNodePositions(canvas);
        var activeNode = null;
        var offsetX = 0;
        var offsetY = 0;

        function onMove(event) {
            if (!activeNode) {
                return;
            }
            var canvasRect = canvas.getBoundingClientRect();
            var left = event.clientX - canvasRect.left + canvas.scrollLeft - offsetX;
            var top = event.clientY - canvasRect.top + canvas.scrollTop - offsetY;
            left = Math.max(0, left);
            top = Math.max(0, top);
            activeNode.style.left = left + "px";
            activeNode.style.top = top + "px";
            renderRelations();
        }

        function onUp() {
            if (!activeNode) {
                return;
            }
            activeNode.classList.remove("is-dragging");
            saveNodePositions(canvas);
            activeNode = null;
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        }

        canvas.querySelectorAll(".node").forEach(function (node) {
            var handle = node.querySelector(".node-header");
            if (!handle) {
                return;
            }
            handle.addEventListener("mousedown", function (event) {
                if (event.button !== 0) {
                    return;
                }
                activeNode = node;
                var nodeRect = node.getBoundingClientRect();
                offsetX = event.clientX - nodeRect.left;
                offsetY = event.clientY - nodeRect.top;
                activeNode.classList.add("is-dragging");
                document.addEventListener("mousemove", onMove);
                document.addEventListener("mouseup", onUp);
                event.preventDefault();
            });
        });
        renderRelations();
    }

    function initFieldDragConnect() {
        var canvas = document.getElementById("relation-canvas");
        if (!canvas) {
            return;
        }
        var buttons = canvas.querySelectorAll(".field-pin");
        if (!buttons.length) {
            return;
        }
        var dragSource = null;
        var hoverTarget = null;

        function clearDragState() {
            buttons.forEach(function (button) {
                button.classList.remove("is-drag-source");
                button.classList.remove("is-drop-target");
            });
            dragSource = null;
            hoverTarget = null;
            previewRelation = null;
            renderRelations();
        }

        buttons.forEach(function (button) {
            button.addEventListener("dragstart", function (event) {
                dragSource = button;
                button.classList.add("is-drag-source");
                if (event.dataTransfer) {
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", button.dataset.fieldId);
                }
                var start = getFieldCenter(canvas, button.dataset.fieldId);
                previewRelation = start ? { start: start, end: start } : null;
                renderRelations();
            });

            button.addEventListener("dragover", function (event) {
                if (!dragSource || dragSource === button) {
                    return;
                }
                if (dragSource.dataset.datasetId === button.dataset.datasetId) {
                    return;
                }
                event.preventDefault();
                buttons.forEach(function (item) {
                    item.classList.remove("is-drop-target");
                });
                button.classList.add("is-drop-target");
                var start = getFieldCenter(canvas, dragSource.dataset.fieldId);
                var end = getFieldCenter(canvas, button.dataset.fieldId);
                previewRelation = start && end ? { start: start, end: end } : null;
                renderRelations();
            });

            button.addEventListener("drop", function (event) {
                if (!dragSource || dragSource === button) {
                    return;
                }
                if (dragSource.dataset.datasetId === button.dataset.datasetId) {
                    return;
                }
                event.preventDefault();
                addPendingRelation(dragSource, button);
                applySelection([]);
                clearDragState();
            });

            button.addEventListener("dragend", function () {
                clearDragState();
            });
        });

        canvas.addEventListener("dragover", function (event) {
            if (!dragSource) {
                return;
            }
            event.preventDefault();
            var start = getFieldCenter(canvas, dragSource.dataset.fieldId);
            var rect = canvas.getBoundingClientRect();
            previewRelation = start ? {
                start: start,
                end: {
                    x: event.clientX - rect.left + canvas.scrollLeft,
                    y: event.clientY - rect.top + canvas.scrollTop
                }
            } : null;
            renderRelations();
        });

        canvas.addEventListener("drop", function () {
            clearDragState();
        });
    }

    window.addEventListener("load", function () {
        initNodeDragging();
        initFieldSelection();
        initFieldDragConnect();
        renderRelations();
        window.addEventListener("resize", renderRelations);
        var canvas = document.getElementById("relation-canvas");
        if (canvas) {
            canvas.addEventListener("scroll", renderRelations);
        }
    });
})();
