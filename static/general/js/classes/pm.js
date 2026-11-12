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
}

const pm = new PM();
