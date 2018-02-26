from __future__ import division

import torch

from .utils import get_func, consecutive


def _preprocess(position, size, batch=None, start=None):
    size = size.type_as(position)

    # Allow one-dimensional positions.
    if position.dim() == 1:
        position = position.unsqueeze(-1)

    assert size.dim() == 1, 'Size tensor must be one-dimensional'
    assert position.size(-1) == size.size(-1), (
        'Last dimension of position tensor must have same size as size tensor')

    # Translate to minimal positive positions if no start was passed.
    if start is None:
        position = position - position.min(dim=-2, keepdim=True)[0]
    else:
        position = position - start
        assert position.min() >= 0, (
            'Passed origin resulting in unallowed negative positions')

    # If given, append batch to position tensor.
    if batch is not None:
        batch = batch.unsqueeze(-1).type_as(position)
        assert position.size()[:-1] == batch.size()[:-1], (
            'Position tensor must have same size as batch tensor apart from '
            'the last dimension')
        position = torch.cat([batch, position], dim=-1)
        size = torch.cat([size.new(1).fill_(1), size], dim=-1)

    return position, size


def _minimal_cluster_size(position, size):
    max = position.max(dim=0)[0]
    while max.dim() > 1:
        max = max.max(dim=0)[0]
    cluster_size = (max / size).long() + 1
    return cluster_size


def _fixed_cluster_size(position, size, batch=None, end=None):
    if end is None:
        return _minimal_cluster_size(position, size)

    eps = 0.000001  # Model [start, end).
    if batch is None:
        cluster_size = ((end / size).float() - eps).long() + 1
    else:
        cluster_size = ((end / size[1:]).float() - eps).long() + 1
        cluster_size = torch.cat([batch.max() + 1, cluster_size], dim=0)

    return cluster_size


def _grid_cluster(position, size, cluster_size):
    C = cluster_size.prod()
    cluster = cluster_size.new(torch.Size(list(position.size())[:-1]))
    cluster = cluster.unsqueeze(dim=-1)

    func = get_func('grid', position)
    func(C, cluster, position, size, cluster_size)

    cluster = cluster.squeeze(dim=-1)
    return cluster, C


def sparse_grid_cluster(position, size, batch=None, start=None):
    position, size = _preprocess(position, size, batch, start)
    cluster_size = _minimal_cluster_size(position, size)
    cluster, C = _grid_cluster(position, size, cluster_size)
    cluster, u = consecutive(cluster)

    if batch is None:
        return cluster
    else:
        batch = u / (C // cluster_size[0])
        return cluster, batch


def dense_grid_cluster(position, size, batch=None, start=None, end=None):
    position, size = _preprocess(position, size, batch, start)
    cluster_size = _fixed_cluster_size(position, size, batch, end)
    cluster, C = _grid_cluster(position, size, cluster_size)

    if batch is None:
        return cluster, C
    else:
        C = C // cluster_size[0]
        return cluster, C
