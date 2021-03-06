
import contextlib
import flask
import mock
import testify as T

from util.auto_namedtuple import auto_namedtuple
import web.flask_helpers
from web.flask_helpers import is_internal
from web.flask_helpers import render_template_mako
from web.flask_helpers import template_lookup

class TestIsInternal(T.TestCase):
    """Tests the @require_internal decorator."""

    def _get_fake_request(self, remote_addr='127.0.0.1'):
        return auto_namedtuple('MockRequest', remote_addr=remote_addr)

    def test_is_internal_with_internal_ip(self):
        with mock.patch.object(flask, 'request', self._get_fake_request()):
            T.assert_equal(is_internal(), True)

    def test_is_internal_with_external_ip(self):
        with mock.patch.object(
            flask,
            'request',
            self._get_fake_request('192.168.0.1'),
        ):
            T.assert_equal(is_internal(), False)


class TestRenderTemplate(T.TestCase):

    @T.setup_teardown
    def setup_mocks(self):
        with contextlib.nested(
            mock.patch.object(web.flask_helpers, 'is_internal', autospec=True),
            mock.patch.object(
                template_lookup, 'get_template', autospec=True
            ),
        ) as (
            self.is_internal_mock,
            self.get_template_mock,
        ):
            yield

    def test_render_template(self):
        kwargs = {
            'foo': 'bar',
            'baz': 'womp',
        }
        ret = render_template_mako(mock.sentinel.template, **kwargs)

        T.assert_equal(
            ret,
            self.get_template_mock.return_value.render.return_value,
        )
        self.is_internal_mock.assert_called_once_with()
        self.get_template_mock.assert_called_once_with(mock.sentinel.template)
        self.get_template_mock.return_value.render.assert_called_once_with(
            is_internal=self.is_internal_mock.return_value,
            **kwargs
        )

if __name__ == '__main__':
    T.run()
