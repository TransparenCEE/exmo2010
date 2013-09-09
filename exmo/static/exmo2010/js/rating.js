// This file is part of EXMO2010 software.
// Copyright 2010, 2011, 2013 Al Nikolov
// Copyright 2010, 2011 non-profit partnership Institute of Information Freedom Development
// Copyright 2012, 2013 Foundation "Institute for Information Freedom Development"
//
//    This program is free software: you can redistribute it and/or modify
//    it under the terms of the GNU Affero General Public License as
//    published by the Free Software Foundation, either version 3 of the
//    License, or (at your option) any later version.
//
//    This program is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//    GNU Affero General Public License for more details.
//
//    You should have received a copy of the GNU Affero General Public License
//    along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
$(document).ready(function() {

    function pseudolinkHandler( e ) {
        var $user_selected = $('#user-selcted');
        $user_selected.removeClass('pseudo-off');
        $user_selected.addClass('pseudo');
        $user_selected.parent('span').removeClass('active');
        $(e.target).removeClass('pseudo');
        $(e.target).addClass('pseudo-off');
        $(e.target).parent('span').addClass('active');

        $('#pselect_div').hide();
        $('#parameters-toggle').hide();

        e.preventDefault();
    }

    function parametersToggle() {
        if($('div.scroll').is(":visible")) {
            $('#parameters-toggle a').html(gettext('Hide parameter list'));
            $('#parameters-toggle').removeClass('arrow-down');
            $('#parameters-toggle').addClass('arrow-up');

        } else {
            $('#parameters-toggle a').html(gettext('Show parameter list'));
            $('#parameters-toggle').removeClass('arrow-up');
            $('#parameters-toggle').addClass('arrow-down');
        }
    }

    $('#user-selcted').click(function( e ) {

        $('.rating-menu > span > span').each(function() {
            $(this).removeClass('pseudo-off');
            $(this).addClass('pseudo');
            $(this).parent('span').removeClass('active');
            $(this).on("click", pseudolinkHandler);
        });

        $('#pselect_div').show();
        $(this).removeClass('pseudo');
        $(this).addClass('pseudo-off');
        $(this).parent('span').addClass('active');
        $('#parameters-toggle').show();

        parametersToggle();

        e.preventDefault();
    });

    $('#parameters-toggle').click(function( e ) {
        $('#pselect_div').toggle();
        parametersToggle();
        e.preventDefault();
    })
});
