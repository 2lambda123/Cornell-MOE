# -*- coding: utf-8 -*-
"""Classes for bandit endpoints.

Includes:
    1. request and response schemas
    2. pretty and backend views
"""
import colander
import copy

from pyramid.view import view_config

from moe.bandit.constant import DEFAULT_EPSILON, EPSILON_SUBTYPE_GREEDY, EPSILON_SUBTYPES
from moe.bandit.linkers import EPSILON_SUBTYPES_TO_EPSILON_METHODS
from moe.views.bandit_pretty_view import BanditPrettyView
from moe.views.constant import BANDIT_EPSILON_ROUTE_NAME, BANDIT_EPSILON_PRETTY_ROUTE_NAME
from moe.views.pretty_view import PRETTY_RENDERER
from moe.views.schemas import ArmAllocations, BanditHistoricalInfo, BANDIT_EPSILON_SUBTYPES_TO_HYPERPARAMETER_INFO_SCHEMA_CLASSES
from moe.views.utils import _make_bandit_historical_info_from_params


class BanditEpsilonRequest(colander.MappingSchema):

    """A bandit_epsilon request colander schema.

    **Required fields**

        :historical_info: a :class:`moe.views.schemas.BanditHistoricalInfo` object of historical data

    **Optional fields**

        :subtype: subtype of the epsilon bandit algorithm (default: greedy)
        :hyperparameter_info: a :class:`moe.views.schemas.BanditEpsilonHyperparameterInfo` dict of hyperparameter information

    **Example Minimal Request**

    .. sourcecode:: http

        Content-Type: text/javascript

        {
                    "historical_info": {
                        "arms_sampled": {
                                "arm1": {"win": 20, "loss": 5, "total": 25},
                                "arm2": {"win": 20, "loss": 10, "total": 30},
                                "arm3": {"win": 0, "loss": 0, "total": 0},
                            },
                        },
        }

    **Example Full Request**

    .. sourcecode:: http

        Content-Type: text/javascript

        {
                    "subtype": "greedy",
                    "historical_info": {
                        "arms_sampled": {
                                "arm1": {"win": 20, "loss": 5, "total": 25},
                                "arm2": {"win": 20, "loss": 10, "total": 30},
                                "arm3": {"win": 0, "loss": 0, "total": 0},
                            },
                        },
                    "hyperparameter_info": {
                        "epsilon": 0.05,
                        },
        }

    """

    subtype = colander.SchemaNode(
            colander.String(),
            validator=colander.OneOf(EPSILON_SUBTYPES),
            missing=EPSILON_SUBTYPE_GREEDY,
            )
    historical_info = BanditHistoricalInfo()
    hyperparameter_info = colander.SchemaNode(
            colander.Mapping(unknown='preserve'),
            missing={},
            )


class BanditEpsilonResponse(colander.MappingSchema):

    """A bandit  response colander schema.

    **Output fields**

        :endpoint: the endpoint that was called
        :arms: a dictionary of (arm name, allocaiton) key-value pairs (:class:`moe.views.schemas.ArmAllocations`)
        :winner: winning arm name

    **Example Response**

    .. sourcecode:: http

    {
                "endpoint":"bandit_epsilon",
                "arms": {
                    "arm1": 0.95,
                    "arm2": 0.025,
                    "arm3": 0.025,
                    }
                "winner": "arm1",
    }

    """

    endpoint = colander.SchemaNode(colander.String())
    arms = ArmAllocations()
    winner = colander.SchemaNode(colander.String())


class BanditEpsilonView(BanditPrettyView):

    """Views for bandit_epsilon endpoints."""

    _route_name = BANDIT_EPSILON_ROUTE_NAME
    _pretty_route_name = BANDIT_EPSILON_PRETTY_ROUTE_NAME

    request_schema = BanditEpsilonRequest()
    response_schema = BanditEpsilonResponse()

    _pretty_default_request = {
            "subtype": EPSILON_SUBTYPE_GREEDY,
            "historical_info": BanditPrettyView._pretty_default_historical_info,
            "hyperparameter_info": {"epsilon": DEFAULT_EPSILON},
            }

    def get_params_from_request(self):
        """Return the deserialized parameters from the json_body of a request.

        We explicitly pull out the ``hyparparameter_info`` and use it to deserialize and validate
        the other parameters (epsilon, total_samples).

        This is necessary because we have different hyperparameters for
        different subtypes.

        :returns: A deserialized self.request_schema object
        :rtype: dict

        """
        # First we get the standard params (not including historical info)
        params = super(BanditEpsilonView, self).get_params_from_request()

        # colander deserialized results are READ-ONLY. We will potentially be overwriting
        # fields of ``params['optimizer_info']``, so we need to copy it first.
        params['hyperparameter_info'] = copy.deepcopy(params['hyperparameter_info'])

        # Find the schma class that corresponds to the ``optimizer_type`` of the request
        # optimizer_parameters has *not been validated yet*, so we need to validate manually.
        schema_class = BANDIT_EPSILON_SUBTYPES_TO_HYPERPARAMETER_INFO_SCHEMA_CLASSES[params['subtype']]()

        # Deserialize and validate the parameters
        validated_hyperparameter_info = schema_class.deserialize(params['hyperparameter_info'])

        # Put the now validated hyperparameter info back into the params dictionary to be consumed by the view
        params['hyperparameter_info'] = validated_hyperparameter_info

        return params

    @view_config(route_name=_pretty_route_name, renderer=PRETTY_RENDERER)
    def pretty_view(self):
        """A pretty, browser interactive view for the interface. Includes form request and response.

        .. http:get:: /bandit/epsilon/pretty

        """
        return self.pretty_response()

    @view_config(route_name=_route_name, renderer='json', request_method='POST')
    def bandit_epsilon_view(self):
        """Endpoint for bandit_epsilon POST requests.

        .. http:post:: /bandit/epsilon

           Predict the optimal arm from a set of arms, given historical data.

           :input: :class:`moe.views.bandit_epsilon.BanditEpsilonRequest`
           :output: :class:`moe.views.bandit_epsilon.BanditEpsilonResponse`

           :status 200: returns a response
           :status 500: server error

        """
        params = self.get_params_from_request()

        subtype = params.get('subtype')
        historical_info = _make_bandit_historical_info_from_params(params)

        bandit_class = EPSILON_SUBTYPES_TO_EPSILON_METHODS[subtype].bandit_class(historical_info=historical_info, **params.get('hyperparameter_info'))

        return self.form_response({
                'endpoint': self._route_name,
                'arms': bandit_class.allocate_arms(),
                'winner': bandit_class.choose_arm(),
                })
