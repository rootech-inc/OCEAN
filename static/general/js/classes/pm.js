class PM {
    constructor() {
        this.endpoint = '/pm/api/';
    }

    getMyPk() {
        return $('#mypk').val();
    }

    // ---- Clients ----
    async listClients() {
        return await api.v2('VIEW', { module: 'client', data: { pk: '*' } }, this.endpoint);
    }

    async getClient(pk) {
        return await api.v2('VIEW', { module: 'client', data: { pk } }, this.endpoint);
    }

    async createClient(payload) {
        return await api.v2('PUT', { module: 'client', data: payload }, this.endpoint);
    }

    async updateClient(payload) {
        return await api.v2('PATCH', { module: 'client', data: payload }, this.endpoint);
    }

    async deleteClient(pk) {
        return await api.v2('DELETE', { module: 'client', data: { pk } }, this.endpoint);
    }

    async uploadClientLogo(pk, file) {
        const formData = new FormData();
        formData.append('pk', pk);
        formData.append('logo', file);
        const res = await fetch('/pm/upload-client-logo/', {
            method: 'POST',
            body: formData,
        });
        return await res.json();
    }

    // ---- Projects ----
    async listProjects(filters = {}) {
        return await api.v2('VIEW', { module: 'project', data: { url: '*', ...filters } }, this.endpoint);
    }

    async getProject(url) {
        return await api.v2('VIEW', { module: 'project', data: { url } }, this.endpoint);
    }

    async createProject(payload) {
        return await api.v2(
            'PUT',
            { module: 'project', data: { ...payload, mypk: this.getMyPk() } },
            this.endpoint
        );
    }

    async updateProject(payload) {
        return await api.v2('PATCH', { module: 'project', data: payload }, this.endpoint);
    }

    async deleteProject(pk) {
        return await api.v2('DELETE', { module: 'project', data: { pk } }, this.endpoint);
    }

    async uploadProjectCover(pk, file) {
        const formData = new FormData();
        formData.append('pk', pk);
        formData.append('cover_image', file);
        const res = await fetch('/pm/upload-project-cover/', {
            method: 'POST',
            body: formData,
        });
        return await res.json();
    }

    // ---- Timeline Updates ----
    async createTimeline(payload) {
        return await api.v2(
            'PUT',
            { module: 'update_timeline', data: { ...payload, mypk: this.getMyPk() } },
            this.endpoint
        );
    }

    async updateTimeline(payload) {
        return await api.v2('PATCH', { module: 'update_timeline', data: payload }, this.endpoint);
    }

    async deleteTimeline(pk) {
        return await api.v2('DELETE', { module: 'update_timeline', data: { pk } }, this.endpoint);
    }

    // ---- Rich Text Editor Helpers (TinyMCE, matching blog) ----
    createEditor(selector, initialHtml = '', height = 320) {
        if (typeof tinymce === 'undefined') return null;
        tinymce.remove(selector);
        const useDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
        tinymce.init({
            selector,
            plugins: 'preview importcss searchreplace autolink directionality code visualblocks visualchars fullscreen image link media table charmap pagebreak nonbreaking anchor insertdatetime advlist lists wordcount help quickbars emoticons',
            menubar: 'file edit view insert format tools table help',
            toolbar: 'undo redo | bold italic underline strikethrough | fontfamily fontsize blocks | alignleft aligncenter alignright alignjustify | outdent indent | numlist bullist | forecolor backcolor removeformat | link image table | code fullscreen preview',
            toolbar_mode: 'sliding',
            height,
            skin: useDarkMode ? 'oxide-dark' : 'oxide',
            content_css: useDarkMode ? 'dark' : 'default',
            content_style: 'body { font-family:Helvetica,Arial,sans-serif; font-size:15px }',
            setup: (editor) => {
                editor.on('init', () => {
                    editor.setContent(initialHtml || '');
                });
            },
        });
        return selector.replace(/^#/, '');
    }

    getEditorHtml(editorId) {
        const ed = typeof tinymce !== 'undefined' ? tinymce.get(editorId) : null;
        return ed ? ed.getContent() : ($(`#${editorId}`).val() || '');
    }

    isEditorEmpty(editorId) {
        const ed = typeof tinymce !== 'undefined' ? tinymce.get(editorId) : null;
        if (!ed) return ($(`#${editorId}`).val() || '').trim().length === 0;
        return ed.getContent({ format: 'text' }).trim().length === 0;
    }

    stripHtml(html) {
        const tmp = document.createElement('div');
        tmp.innerHTML = html || '';
        return (tmp.textContent || tmp.innerText || '').trim();
    }

    sanitizeHtml(html) {
        const tmp = document.createElement('div');
        tmp.innerHTML = html || '';
        tmp.querySelectorAll('script, style, iframe, object, embed').forEach(node => node.remove());
        tmp.querySelectorAll('*').forEach(el => {
            [...el.attributes].forEach(attr => {
                if (attr.name.toLowerCase().startsWith('on')) {
                    el.removeAttribute(attr.name);
                }
            });
        });
        return tmp.innerHTML;
    }
}

const pm = new PM();
