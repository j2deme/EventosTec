/**
 * Admin Settings Manager - Alpine.js component
 * Manages application configuration through admin UI
 */

function settingsManager() {
  return {
    settings: [],
    loading: false,
    saving: false,
    error: null,
    success: null,
    editingKey: null,
    editingValue: null,

    /**
     * Initialize: Load all settings
     */
    async init() {
      await this.loadSettings();
    },

    /**
     * Load all settings from API
     */
    async loadSettings() {
      this.loading = true;
      this.error = null;
      try {
        const response = await fetch("/admin/api/settings", {
          method: "GET",
          headers: getAuthHeaders(),
        });
        if (!response.ok) throw new Error("Failed to load settings");
        const data = await response.json();
        this.settings = data.settings;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Start editing a setting
     */
    startEdit(key, currentValue) {
      this.editingKey = key;
      this.editingValue = currentValue || "";
    },

    /**
     * Cancel editing
     */
    cancelEdit() {
      this.editingKey = null;
      this.editingValue = null;
    },

    /**
     * Save a setting value
     */
    async saveSetting() {
      if (!this.editingKey) return;

      this.saving = true;
      this.error = null;
      try {
        const response = await fetch(`/admin/api/settings/${this.editingKey}`, {
          method: "PUT",
          headers: getAuthHeaders(),
          body: JSON.stringify({ value: this.editingValue }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || "Failed to save setting");
        }

        this.success = `Setting "${this.editingKey}" updated`;
        setTimeout(() => (this.success = null), 3000);

        await this.loadSettings();
        this.cancelEdit();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.saving = false;
      }
    },

    /**
     * Reset a setting to its default value
     */
    async resetToDefault(key) {
      if (!confirm(`Reset "${key}" to default?`)) return;

      this.saving = true;
      this.error = null;
      try {
        const response = await fetch(`/admin/api/settings/${key}/reset`, {
          method: "POST",
          headers: getAuthHeaders(),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || "Failed to reset setting");
        }

        this.success = `Setting "${key}" reset to default`;
        setTimeout(() => (this.success = null), 3000);

        await this.loadSettings();
      } catch (err) {
        this.error = err.message;
      } finally {
        this.saving = false;
      }
    },

    /**
     * Get display value based on data type
     */
    getDisplayValue(setting) {
      if (!setting.value) return "(no establecido)";
      if (setting.data_type === "boolean") {
        return setting.value === "true" || setting.value === "1"
          ? "✓ Habilitado"
          : "✗ Deshabilitado";
      }
      return setting.value;
    },

    /**
     * Get input type for data_type
     */
    getInputType(dataType) {
      if (dataType === "integer") return "number";
      if (dataType === "boolean") return "checkbox";
      return "text";
    },
  };
}

// Expose for Node testing
if (typeof module !== "undefined" && module.exports) {
  module.exports = settingsManager;
}
