# Copyright 2017, Google LLC All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import threading

import mock
from six.moves import queue

from google.cloud.pubsub_v1.subscriber import _helper_threads


def test_start():
    registry = _helper_threads.HelperThreadRegistry()
    queue_ = queue.Queue()
    target = mock.Mock(spec=())
    with mock.patch.object(threading.Thread, 'start', autospec=True) as start:
        registry.start('foo', queue_, target)
        assert start.called


def test_stop_noop():
    registry = _helper_threads.HelperThreadRegistry()
    assert len(registry._helper_threads) == 0
    registry.stop('foo')
    assert len(registry._helper_threads) == 0


@mock.patch.object(
    _helper_threads, '_current_thread', return_value=mock.sentinel.thread)
def test_stop_current_thread(_current_thread):
    registry = _helper_threads.HelperThreadRegistry()
    queue_ = mock.Mock(spec=('put',))

    name = 'here'
    registry._helper_threads[name] = _helper_threads._HelperThread(
        name=name,
        queue_put=queue_.put,
        thread=_current_thread.return_value,
    )
    assert list(registry._helper_threads.keys()) == [name]
    registry.stop(name)
    # Make sure it hasn't been removed from the registry ...
    assert list(registry._helper_threads.keys()) == [name]
    # ... but it did receive the STOP signal.
    queue_.put.assert_called_once_with(_helper_threads.STOP)

    # Verify that our mock was only called once.
    _current_thread.assert_called_once_with()


def test_stop_dead_thread():
    registry = _helper_threads.HelperThreadRegistry()
    registry._helper_threads['foo'] = _helper_threads._HelperThread(
        name='foo',
        queue_put=None,
        thread=threading.Thread(target=lambda: None),
    )
    assert len(registry._helper_threads) == 1
    registry.stop('foo')
    assert len(registry._helper_threads) == 0


@mock.patch.object(queue.Queue, 'put')
@mock.patch.object(threading.Thread, 'is_alive')
@mock.patch.object(threading.Thread, 'join')
def test_stop_alive_thread(join, is_alive, put):
    is_alive.return_value = True

    # Set up a registry with a helper thread in it.
    registry = _helper_threads.HelperThreadRegistry()
    queue_ = queue.Queue()
    registry._helper_threads['foo'] = _helper_threads._HelperThread(
        name='foo',
        queue_put=queue_.put,
        thread=threading.Thread(target=lambda: None),
    )

    # Assert that the helper thread is present, and removed correctly
    # on stop.
    assert len(registry._helper_threads) == 1
    registry.stop('foo')
    assert len(registry._helper_threads) == 0

    # Assert that all of our mocks were called in the expected manner.
    is_alive.assert_called_once_with()
    join.assert_called_once_with()
    put.assert_called_once_with(_helper_threads.STOP)


def test_stop_all():
    registry = _helper_threads.HelperThreadRegistry()
    registry._helper_threads['foo'] = _helper_threads._HelperThread(
        name='foo',
        queue_put=None,
        thread=threading.Thread(target=lambda: None),
    )
    assert len(registry._helper_threads) == 1
    registry.stop_all()
    assert len(registry._helper_threads) == 0


def test_stop_all_noop():
    registry = _helper_threads.HelperThreadRegistry()
    assert len(registry._helper_threads) == 0
    registry.stop_all()
    assert len(registry._helper_threads) == 0


def test_queue_callback_worker():
    queue_ = queue.Queue()
    callback = mock.Mock(spec=())
    qct = _helper_threads.QueueCallbackWorker(queue_, callback)

    # Set up an appropriate mock for the queue, and call the queue callback
    # thread.
    with mock.patch.object(queue.Queue, 'get') as get:
        item1 = ('action', mock.sentinel.A)
        get.side_effect = (item1, _helper_threads.STOP)
        qct()

        # Assert that we got the expected calls.
        assert get.call_count == 2
        callback.assert_called_once_with('action', mock.sentinel.A)


def test_queue_callback_worker_exception():
    queue_ = queue.Queue()
    callback = mock.Mock(spec=(), side_effect=(Exception,))
    qct = _helper_threads.QueueCallbackWorker(queue_, callback)

    # Set up an appropriate mock for the queue, and call the queue callback
    # thread.
    with mock.patch.object(queue.Queue, 'get') as get:
        item1 = ('action', mock.sentinel.A)
        get.side_effect = (item1, _helper_threads.STOP)
        qct()

        # Assert that we got the expected calls.
        assert get.call_count == 2
        callback.assert_called_once_with('action', mock.sentinel.A)