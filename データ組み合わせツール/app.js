(function () {
    var previewRelation = null;
    var pendingRelations = [];
    var zoomScale = 1;
    var activeDatasetIds = [];

    function getStage() {
        return document.getElementById("relation-stage");
    }

    function getCanvas() {
        return document.getElementById("relation-canvas");
    }

    function getNode(datasetId) {
        var stage = getStage();
        if (!stage) {
            return null;
        }
        return stage.querySelector('.node[data-dataset-id="' + datasetId + '"]');
    }

    function getActiveDatasetStorageKey() {
        return "data-link-tool-active-datasets:" + window.location.pathname;
    }

    function saveActiveDatasets() {
        try {
            window.localStorage.setItem(getActiveDatasetStorageKey(), JSON.stringify(activeDatasetIds));
        } catch (error) {
        }
    }

    function loadActiveDatasets() {
        var raw = "";
        try {
            raw = window.localStorage.getItem(getActiveDatasetStorageKey()) || "";
        } catch (error) {
            raw = "";
        }
        if (!raw) {
            activeDatasetIds = [];
            return;
        }
        try {
            activeDatasetIds = JSON.parse(raw) || [];
        } catch (error) {
            activeDatasetIds = [];
        }
    }

    function syncDatasetPalette() {
        var palette = document.getElementById("dataset-palette-list");
        if (!palette) {
            return;
        }
        var chips = palette.querySelectorAll(".dataset-chip");
        chips.forEach(function (chip) {
            var isActive = activeDatasetIds.indexOf(String(chip.dataset.datasetSourceId)) !== -1;
            chip.style.display = isActive ? "none" : "inline-flex";
        });
    }

    function syncActiveNodes() {
        var stage = getStage();
        if (!stage) {
            return;
        }
        var nodes = stage.querySelectorAll(".node");
        nodes.forEach(function (node) {
            var isActive = activeDatasetIds.indexOf(String(node.dataset.datasetId)) !== -1;
            node.classList.toggle("is-hidden", !isActive);
        });
        syncDatasetPalette();
        renderRelations();
    }

    function activateDataset(datasetId, left, top) {
        datasetId = String(datasetId);
        if (activeDatasetIds.indexOf(datasetId) === -1) {
            activeDatasetIds.push(datasetId);
        }
        var node = getNode(datasetId);
        if (node) {
            if (typeof left === "number") {
                node.style.left = Math.max(0, left) + "px";
            }
            if (typeof top === "number") {
                node.style.top = Math.max(0, top) + "px";
            }
        }
        saveActiveDatasets();
        syncActiveNodes();
        if (node) {
            saveNodePositions(getStage());
        }
    }

    function deactivateDataset(datasetId) {
        datasetId = String(datasetId);
        activeDatasetIds = activeDatasetIds.filter(function (value) {
            return String(value) !== datasetId;
        });
        pendingRelations = pendingRelations.filter(function (relation) {
            var leftNode = getNodeByFieldId(relation.leftFieldId);
            var rightNode = getNodeByFieldId(relation.rightFieldId);
            if (!leftNode || !rightNode) {
                return false;
            }
            return leftNode.dataset.datasetId !== datasetId && rightNode.dataset.datasetId !== datasetId;
        });
        previewRelation = null;
        saveActiveDatasets();
        syncActiveNodes();
        renderPendingRelations();
    }

    function getNodeByFieldId(fieldId) {
        var stage = getStage();
        if (!stage) {
            return null;
        }
        var target = stage.querySelector('[data-field-id="' + fieldId + '"]');
        return target ? target.closest(".node") : null;
    }

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

    function parseEditingTemplateRelations() {
        var element = document.getElementById("editing-template-relations");
        if (!element) {
            return [];
        }
        try {
            return JSON.parse(element.textContent || "[]");
        } catch (error) {
            return [];
        }
    }

    function ensurePendingRelationNodes() {
        pendingRelations.forEach(function (relation) {
            var leftNode = getNodeByFieldId(relation.leftFieldId);
            var rightNode = getNodeByFieldId(relation.rightFieldId);
            if (leftNode) {
                activateDataset(leftNode.dataset.datasetId);
            }
            if (rightNode) {
                activateDataset(rightNode.dataset.datasetId);
            }
        });
    }

    function initEditingTemplateRelations() {
        var editingRelations = parseEditingTemplateRelations();
        if (!editingRelations.length) {
            return;
        }
        pendingRelations = editingRelations.filter(function (relation) {
            return relation && relation.leftFieldId && relation.rightFieldId;
        }).map(function (relation) {
            return {
                leftFieldId: String(relation.leftFieldId),
                rightFieldId: String(relation.rightFieldId),
                leftLabel: relation.leftLabel,
                rightLabel: relation.rightLabel
            };
        });
        ensurePendingRelationNodes();
        renderPendingRelations();
    }

    function getFieldCenter(container, fieldId) {
        var target = container.querySelector('[data-field-id="' + fieldId + '"]');
        if (!target) {
            return null;
        }
        var node = target.closest(".node");
        if (node && node.classList.contains("is-hidden")) {
            return null;
        }
        var stage = getStage();
        var containerRect = stage ? stage.getBoundingClientRect() : container.getBoundingClientRect();
        var rect = target.getBoundingClientRect();
        return {
            x: (rect.left - containerRect.left) / zoomScale + rect.width / zoomScale / 2,
            y: (rect.top - containerRect.top) / zoomScale + rect.height / zoomScale / 2
        };
    }

    function updateZoomUi() {
        var status = document.getElementById("zoom-status");
        var stage = getStage();
        if (status) {
            status.textContent = Math.round(zoomScale * 100) + "%";
        }
        if (stage) {
            stage.style.transform = "scale(" + zoomScale + ")";
            stage.style.width = Math.max(100, 100 / zoomScale) + "%";
            stage.style.height = Math.max(680, 680 / zoomScale) + "px";
        }
        renderRelations();
    }

    function setZoom(nextScale) {
        zoomScale = Math.min(2, Math.max(0.5, nextScale));
        updateZoomUi();
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
        var canvas = getCanvas();
        var stage = getStage();
        var svg = document.getElementById("relation-svg");
        if (!canvas || !svg || !stage) {
            return;
        }
        var width = Math.max(stage.scrollWidth, stage.offsetWidth);
        var height = Math.max(stage.scrollHeight, stage.offsetHeight);
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

    function syncPendingRelationsInput() {
        ["pending-relations", "template-pending-relations"].forEach(function (inputId) {
            var input = document.getElementById(inputId);
            if (input) {
                input.value = JSON.stringify(pendingRelations);
            }
        });
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

    function initPendingRelationActions() {
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

        var templateForm = document.getElementById("template-form");
        if (templateForm) {
            templateForm.addEventListener("submit", function () {
                syncPendingRelationsInput();
            });
        }

        initEditingTemplateRelations();
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
        var canvas = getCanvas();
        var stage = getStage();
        if (!canvas || !stage) {
            return;
        }
        loadActiveDatasets();
        loadNodePositions(stage);
        syncActiveNodes();
        var activeNode = null;
        var offsetX = 0;
        var offsetY = 0;

        function onMove(event) {
            if (!activeNode) {
                return;
            }
            var stageRect = stage.getBoundingClientRect();
            var left = (event.clientX - stageRect.left) / zoomScale - offsetX;
            var top = (event.clientY - stageRect.top) / zoomScale - offsetY;
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
            saveNodePositions(stage);
            activeNode = null;
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
        }

        stage.querySelectorAll(".node").forEach(function (node) {
            var handle = node.querySelector(".node-header");
            if (!handle) {
                return;
            }
            handle.addEventListener("mousedown", function (event) {
                if (node.classList.contains("is-hidden")) {
                    return;
                }
                if (event.button !== 0) {
                    return;
                }
                activeNode = node;
                var nodeLeft = parseFloat(node.style.left || "0");
                var nodeTop = parseFloat(node.style.top || "0");
                var stageRect = stage.getBoundingClientRect();
                offsetX = (event.clientX - stageRect.left) / zoomScale - nodeLeft;
                offsetY = (event.clientY - stageRect.top) / zoomScale - nodeTop;
                activeNode.classList.add("is-dragging");
                document.addEventListener("mousemove", onMove);
                document.addEventListener("mouseup", onUp);
                event.preventDefault();
            });
        });
        renderRelations();
    }

    function initFieldDragConnect() {
        var canvas = getCanvas();
        var stage = getStage();
        if (!canvas || !stage) {
            return;
        }
        var buttons = stage.querySelectorAll(".field-pin");
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
            var rect = stage.getBoundingClientRect();
            previewRelation = start ? {
                start: start,
                end: {
                    x: (event.clientX - rect.left) / zoomScale,
                    y: (event.clientY - rect.top) / zoomScale
                }
            } : null;
            renderRelations();
        });

        canvas.addEventListener("drop", function () {
            clearDragState();
        });
    }

    function initDatasetPalette() {
        var canvas = getCanvas();
        var stage = getStage();
        var palette = document.getElementById("dataset-palette-list");
        if (!canvas || !stage || !palette) {
            return;
        }
        var draggingDatasetId = "";

        palette.querySelectorAll(".dataset-chip").forEach(function (chip) {
            chip.addEventListener("dragstart", function (event) {
                draggingDatasetId = String(chip.dataset.datasetSourceId || "");
                if (event.dataTransfer) {
                    event.dataTransfer.effectAllowed = "copy";
                    event.dataTransfer.setData("text/plain", draggingDatasetId);
                }
            });
            chip.addEventListener("dragend", function () {
                draggingDatasetId = "";
                canvas.classList.remove("is-drop-active");
            });
        });

        canvas.addEventListener("dragover", function (event) {
            if (!draggingDatasetId) {
                return;
            }
            event.preventDefault();
            canvas.classList.add("is-drop-active");
        });

        canvas.addEventListener("dragleave", function (event) {
            if (event.target === canvas) {
                canvas.classList.remove("is-drop-active");
            }
        });

        canvas.addEventListener("drop", function (event) {
            if (!draggingDatasetId) {
                return;
            }
            event.preventDefault();
            canvas.classList.remove("is-drop-active");
            var rect = stage.getBoundingClientRect();
            activateDataset(
                draggingDatasetId,
                (event.clientX - rect.left) / zoomScale - 140,
                (event.clientY - rect.top) / zoomScale - 28
            );
            draggingDatasetId = "";
        });
    }

    function initNodeRemoveActions() {
        var stage = getStage();
        if (!stage) {
            return;
        }
        stage.querySelectorAll(".node-remove-btn").forEach(function (button) {
            button.addEventListener("click", function (event) {
                deactivateDataset(button.dataset.removeDatasetId || "");
                event.preventDefault();
                event.stopPropagation();
            });
        });
    }

    function initCanvasZoom() {
        var canvas = getCanvas();
        if (!canvas) {
            return;
        }
        var zoomIn = document.getElementById("zoom-in-btn");
        var zoomOut = document.getElementById("zoom-out-btn");
        var zoomReset = document.getElementById("zoom-reset-btn");
        if (zoomIn) {
            zoomIn.addEventListener("click", function () {
                setZoom(zoomScale + 0.1);
            });
        }
        if (zoomOut) {
            zoomOut.addEventListener("click", function () {
                setZoom(zoomScale - 0.1);
            });
        }
        if (zoomReset) {
            zoomReset.addEventListener("click", function () {
                setZoom(1);
            });
        }
        canvas.addEventListener("wheel", function (event) {
            if (event.target && event.target.closest(".builder-side")) {
                return;
            }
            event.preventDefault();
            setZoom(zoomScale + (event.deltaY < 0 ? 0.1 : -0.1));
        }, { passive: false });
        updateZoomUi();
    }

    window.addEventListener("load", function () {
        initCanvasZoom();
        initNodeDragging();
        initPendingRelationActions();
        initFieldDragConnect();
        initDatasetPalette();
        initNodeRemoveActions();
        renderRelations();
        window.addEventListener("resize", renderRelations);
        var canvas = document.getElementById("relation-canvas");
        if (canvas) {
            canvas.addEventListener("scroll", renderRelations);
        }
    });
})();
