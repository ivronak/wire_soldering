/**
 * erp-list-picker.js
 * Dropdown lists (Category, Branch, etc.) pe "+ Add" aur "Manage" lagane ka shared helper.
 * Soft-remove only — list se hataata hai, hard-delete nahi (audit/business data rule).
 * Use: mountListPicker({ selectId, itemLabel, addPanelId, managePanelId, ... })
 */
(function (global) {
  function $(id) {
    return document.getElementById(id);
  }

  function optionLabel(opt) {
    return (opt.textContent || '').trim();
  }

  function isPlaceholder(opt, placeholderValue) {
    if (!opt) return true;
    if (placeholderValue !== undefined && opt.value === placeholderValue) return true;
    if (!opt.value && !optionLabel(opt)) return true;
    // "Select …" style empty value
    if (opt.value === '' && /select/i.test(optionLabel(opt))) return true;
    return false;
  }

  function listRealOptions(select, placeholderValue) {
    return Array.from(select.options).filter(function (opt) {
      return !isPlaceholder(opt, placeholderValue);
    });
  }

  /**
   * @param {object} cfg
   * @param {string} cfg.selectId
   * @param {string} cfg.itemLabel - toast text me "category" / "branch"
   * @param {string} cfg.addBtnId
   * @param {string} cfg.manageBtnId
   * @param {string} cfg.addPanelId
   * @param {string} cfg.managePanelId
   * @param {string} cfg.addNameId - input for new name
   * @param {string} cfg.addSaveBtnId
   * @param {string} cfg.addCancelBtnId
   * @param {string} cfg.manageListId - ul/div where rows render
   * @param {string} [cfg.manageDoneBtnId]
   * @param {string} [cfg.placeholderValue] - empty option value to skip
   * @param {function} [cfg.slugify] - optional value from name
   */
  function mountListPicker(cfg) {
    var select = $(cfg.selectId);
    var addPanel = $(cfg.addPanelId);
    var managePanel = $(cfg.managePanelId);
    var addName = $(cfg.addNameId);
    var manageList = $(cfg.manageListId);
    var itemLabel = cfg.itemLabel || 'item';
    var placeholderValue = cfg.placeholderValue;
    var slugify =
      cfg.slugify ||
      function (name) {
        return name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '_')
          .replace(/^_|_$/g, '');
      };

    function hidePanels() {
      if (addPanel) addPanel.classList.add('hidden');
      if (managePanel) managePanel.classList.add('hidden');
      if (addName) addName.value = '';
    }

    function showAdd() {
      if (managePanel) managePanel.classList.add('hidden');
      if (addPanel) addPanel.classList.remove('hidden');
      if (addName) addName.focus();
    }

    function showManage() {
      if (addPanel) addPanel.classList.add('hidden');
      if (addName) addName.value = '';
      renderManage();
      if (managePanel) managePanel.classList.remove('hidden');
    }

    function findByLabel(name) {
      var lower = name.toLowerCase();
      return listRealOptions(select, placeholderValue).find(function (opt) {
        return optionLabel(opt).toLowerCase() === lower;
      });
    }

    function addItem(name) {
      name = (name || '').trim();
      if (!name) {
        showToast((itemLabel.charAt(0).toUpperCase() + itemLabel.slice(1)) + ' name is required.', 'error');
        return false;
      }
      var existing = findByLabel(name);
      if (existing) {
        select.value = existing.value;
        showToast('Already in the list — selected for you.', 'info');
        hidePanels();
        return true;
      }
      var opt = document.createElement('option');
      opt.value = slugify(name) || name;
      opt.textContent = name;
      select.appendChild(opt);
      select.value = opt.value;
      hidePanels();
      showToast((itemLabel.charAt(0).toUpperCase() + itemLabel.slice(1)) + ' added: ' + name, 'success');
      return true;
    }

    function renderManage() {
      if (!manageList) return;
      manageList.innerHTML = '';
      var opts = listRealOptions(select, placeholderValue);
      if (opts.length === 0) {
        manageList.innerHTML =
          '<p class="text-[12.5px] text-ink-faint py-1">No items yet. Use + Add to create one.</p>';
        return;
      }
      opts.forEach(function (opt) {
        var row = document.createElement('div');
        row.className = 'flex items-center gap-2 py-1.5 border-b border-slate-200 last:border-0';
        row.setAttribute('data-value', opt.value);

        var nameSpan = document.createElement('span');
        nameSpan.className = 'flex-1 min-w-0 text-[13px] font-medium text-ink truncate';
        nameSpan.textContent = optionLabel(opt);

        var renameBtn = document.createElement('button');
        renameBtn.type = 'button';
        renameBtn.className = 'px-2 py-1 text-[11.5px] font-semibold text-copper-text border border-copper-border bg-white rounded hover:bg-copper hover:text-white';
        renameBtn.textContent = 'Rename';

        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'px-2 py-1 text-[11.5px] font-semibold text-stop border border-stop-border bg-stop-bg rounded hover:opacity-90';
        removeBtn.textContent = 'Remove';

        renameBtn.addEventListener('click', function () {
          // Inline rename: span → input
          if (row.querySelector('input')) return;
          var input = document.createElement('input');
          input.type = 'text';
          input.value = optionLabel(opt);
          input.className =
            'flex-1 min-w-0 px-2 py-1 text-[13px] border border-copper rounded focus:ring-1 focus:ring-copper';
          var saveBtn = document.createElement('button');
          saveBtn.type = 'button';
          saveBtn.className =
            'px-2 py-1 text-[11.5px] font-semibold text-white bg-copper border border-copper-dark rounded';
          saveBtn.textContent = 'Save';
          var cancelBtn = document.createElement('button');
          cancelBtn.type = 'button';
          cancelBtn.className = 'px-2 py-1 text-[11.5px] text-ink-faint hover:bg-white rounded';
          cancelBtn.textContent = 'Cancel';

          row.innerHTML = '';
          row.appendChild(input);
          row.appendChild(saveBtn);
          row.appendChild(cancelBtn);
          input.focus();
          input.select();

          function commit() {
            var newName = input.value.trim();
            if (!newName) {
              showToast('Name cannot be empty.', 'error');
              return;
            }
            var clash = findByLabel(newName);
            if (clash && clash !== opt) {
              showToast('Another ' + itemLabel + ' already has that name.', 'error');
              return;
            }
            opt.textContent = newName;
            // value same rehne do taaki purane form refs toot na jayein (mock)
            showToast('Renamed to ' + newName, 'success');
            renderManage();
          }
          saveBtn.addEventListener('click', commit);
          cancelBtn.addEventListener('click', renderManage);
          input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
              e.preventDefault();
              commit();
            }
            if (e.key === 'Escape') renderManage();
          });
        });

        removeBtn.addEventListener('click', function () {
          // Soft remove — option list se hatao, DB hard-delete nahi (mock)
          var wasSelected = select.value === opt.value;
          var label = optionLabel(opt);
          opt.remove();
          if (wasSelected) {
            // pehla real option ya placeholder
            var next = listRealOptions(select, placeholderValue)[0];
            select.value = next ? next.value : placeholderValue !== undefined ? placeholderValue : '';
          }
          showToast(label + ' removed from list (soft). Old records can still show this name.', 'info');
          renderManage();
        });

        row.appendChild(nameSpan);
        row.appendChild(renameBtn);
        row.appendChild(removeBtn);
        manageList.appendChild(row);
      });
    }

    if (cfg.wireAdd !== false) {
      $(cfg.addBtnId).addEventListener('click', showAdd);
      $(cfg.addCancelBtnId).addEventListener('click', hidePanels);
      $(cfg.addSaveBtnId).addEventListener('click', function () {
        addItem(addName.value);
      });
      if (addName) {
        addName.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') {
            e.preventDefault();
            addItem(addName.value);
          }
        });
      }
    }
    $(cfg.manageBtnId).addEventListener('click', showManage);
    if (cfg.manageDoneBtnId && $(cfg.manageDoneBtnId)) {
      $(cfg.manageDoneBtnId).addEventListener('click', hidePanels);
    }

    return { hidePanels: hidePanels, addItem: addItem, showAdd: showAdd, showManage: showManage };
  }

  global.mountListPicker = mountListPicker;
})(window);
