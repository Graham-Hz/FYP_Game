---
license: cc0-1.0
task_categories:
- sentence-similarity
- summarization
- feature-extraction
tags:
- games
- video-games
---
<p align="center">
  <img src="https://cdn-uploads.huggingface.co/production/uploads/65e3c559d26b426e3e1994f8/K1y9VHwRZrU0dfyQDJdgW.png" />
</p>



<div align="center">
  
  ![visitors](https://visitor-badge.laobi.icu/badge?page_id=atalaydenknalbant/rawg-games-dataset)

</div>

<h6 style="text-align: center;"><strong>Description</strong></h6>
<p style="text-align: center;">
  <strong>Video Games Dataset</strong> video game records data gathered directly from the RAWG API.
  It includes essential fields such as game id, title, release date, rating, genres, platforms, descriptive tags, 
  Metacritic score, developers, publishers, playtime, and a detailed description. The data was collected to support 
  studies, trend analysis, and insights into the gaming industry. Each field is aligned with the specifications provided in the RAWG API documentation.
</p>

<p style="text-align: center;"><strong>Last Dataset Update: June 28, 2026</strong></p>

<h6 style="text-align: center;"><strong>Acknowledgements</strong></h6>

<p style="text-align: center;">
  Grateful to <a href="https://rawg.io/apidocs">RAWG</a> for data API.
</p>

<style>
  table {
    border-collapse: collapse;
    margin: 0 auto; /* This centers the table horizontally */
  }
  th, td {
    border: 1px solid #000;
    padding: 10px;
  }
  .field-column {
    font-weight: 900; /* For a "solid" appearance */
  }
</style>

<table border="0" cellspacing="0">
  <colgroup>
    <col style="border-right: 1px solid #000;">
    <col>
  </colgroup>
  <tr>
    <th class="field-column">Field</th>
    <th class="field-column">Description</th>
  </tr>
  <tr>
    <td class="field-column">id</td>
    <td>A unique identifier for each game, serving as the primary key to reference detailed game data via the API.</td>
  </tr>
  <tr>
    <td class="field-column">slug</td>
    <td>A URL-friendly string derived from the game's name, used for accessing the game's page.</td>
  </tr>
  <tr>
    <td class="field-column">name</td>
    <td>The official title of the game.</td>
  </tr>
  <tr>
    <td class="field-column">released</td>
    <td>The release date of the game, typically in the YYYY-MM-DD format.</td>
  </tr>
  <tr>
    <td class="field-column">tba</td>
    <td>A boolean field indicating if the game's release date is "To Be Announced".</td>
  </tr>
  <tr>
    <td class="field-column">background_image</td>
    <td>The URL for the main promotional image of the game.</td>
  </tr>
  <tr>
    <td class="field-column">rating</td>
    <td>An aggregated score based on player reviews, computed on a standardized scale reflecting user opinions.</td>
  </tr>
  <tr>
    <td class="field-column">rating_top</td>
    <td>Rounded number of rating</td>
  </tr>
  <tr>
    <td class="field-column">ratings_count</td>
    <td>The total number of ratings the game has received from users.</td>
  </tr>
  <tr>
    <td class="field-column">reviews_text_count</td>
    <td>The count of user-submitted text reviews for the game.</td>
  </tr>
  <tr>
    <td class="field-column">added</td>
    <td>The total number of RAWG users who have added this game to their library.</td>
  </tr>
  <tr>
    <td class="field-column">metacritic</td>
    <td>A numerical score derived from Metacritic reviews (usually ranging from 0 to 100).</td>
  </tr>
  <tr>
    <td class="field-column">playtime</td>
    <td>An estimate of the average time (in hours) that players spend engaging with the game.</td>
  </tr>
  <tr>
    <td class="field-column">suggestions_count</td>
    <td>The number of other games suggested as similar to this one.</td>
  </tr>
  <tr>
    <td class="field-column">updated</td>
    <td>The timestamp of the last update to the game's data entry.</td>
  </tr>
  <tr>
    <td class="field-column">reviews_count</td>
    <td>The total count of reviews for the game.</td>
  </tr>
  <tr>
    <td class="field-column">saturated_color</td>
    <td>A hexadecimal color code representing a saturated color from the game's promotional images.</td>
  </tr>
  <tr>
    <td class="field-column">dominant_color</td>
    <td>A hexadecimal color code for the dominant color found in the game's artwork.</td>
  </tr>
  <tr>
    <td class="field-column">platforms</td>
    <td>An array of platform objects that indicate on which systems the game is available (e.g., PC, PlayStation, Xbox).</td>
  </tr>
  <tr>
    <td class="field-column">stores</td>
    <td>An array of store objects where the game can be purchased (e.g., Steam, PlayStation Store).</td>
  </tr>
  <tr>
    <td class="field-column">developers</td>
    <td>The individuals or companies responsible for creating the game.</td>
  </tr>
  <tr>
    <td class="field-column">genres</td>
    <td>A list of genre objects categorizing the game (e.g., Action, Adventure, RPG).</td>
  </tr>
  <tr>
    <td class="field-column">tags</td>
    <td>A collection of descriptive keyword tags (e.g., multiplayer, indie).</td>
  </tr>
  <tr>
    <td class="field-column">publishers</td>
    <td>Entities that market and distribute the game.</td>
  </tr>
  <tr>
    <td class="field-column">esrb_rating</td>
    <td>The ESRB rating object, which includes the rating name (e.g., 'Mature', 'Teen').</td>
  </tr>
  <tr>
    <td class="field-column">description_raw</td>
    <td>A plain text, unformatted version of the game's description.</td>
  </tr>
  <tr>
    <td class="field-column">added_by_status</td>
    <td>An object detailing the status of the game in users' libraries (e.g., yet, owned, beaten, toplay, dropped, playing).</td>
  </tr>
  <tr>
    <td class="field-column">metacritic_url</td>
    <td>The direct URL to the game's page on the Metacritic website.</td>
  </tr>
  <tr>
    <td class="field-column">description</td>
    <td>A detailed narrative of the game, providing in-depth information about gameplay, plot, mechanics, and overall context.</td>
  </tr>
  <tr>
    <td class="field-column">ratings</td>
    <td>An object containing the distribution of ratings, showing the count for each rating level.</td>
  </tr>
  <tr>
    <td class="field-column">clip</td>
    <td>A URL for a short video clip or trailer of the game.</td>
  </tr>
  <tr>
    <td class="field-column">name_original</td>
    <td>The game's original title, if it differs from the primary 'name' field.</td>
  </tr>
  <tr>
    <td class="field-column">community_rating</td>
    <td>A rating given by the RAWG community.</td>
  </tr>
  <tr>
    <td class="field-column">reddit_url</td>
    <td>The URL of the game's official or primary subreddit.</td>
  </tr>
  <tr>
    <td class="field-column">reddit_name</td>
    <td>The name of the game's subreddit (e.g., 'r/gaming').</td>
  </tr>
  <tr>
    <td class="field-column">user_game</td>
    <td>User-specific game data. This field is null if the user is not authenticated.</td>
  </tr>
  <tr>
    <td class="field-column">movies_count</td>
    <td>The number of video files (trailers, etc.) associated with the game.</td>
  </tr>
  <tr>
    <td class="field-column">reddit_description</td>
    <td>The description of the game's subreddit.</td>
  </tr>
  <tr>
    <td class="field-column">reactions</td>
    <td>An object with counts of different user reactions to the game.</td>
  </tr>
  <tr>
    <td class="field-column">parents_count</td>
    <td>The number of main games in the series, used for DLCs and special editions.</td>
  </tr>
  <tr>
    <td class="field-column">background_image_additional</td>
    <td>URL for an additional promotional image for the game.</td>
  </tr>
  <tr>
    <td class="field-column">website</td>
    <td>The URL of the game's official website.</td>
  </tr>
  <tr>
    <td class="field-column">reddit_count</td>
    <td>The number of Reddit posts about the game.</td>
  </tr>
  <tr>
    <td class="field-column">achievements_count</td>
    <td>The total number of unlockable achievements in the game.</td>
  </tr>
  <tr>
    <td class="field-column">youtube_count</td>
    <td>The number of YouTube videos related to the game.</td>
  </tr>
  <tr>
    <td class="field-column">short_screenshots</td>
    <td>A list of URLs for smaller, optimized screenshots.</td>
  </tr>
  <tr>
    <td class="field-column">creators_count</td>
    <td>The number of individual creators (developers, etc.) associated with the game.</td>
  </tr>
  <tr>
    <td class="field-column">twitch_count</td>
    <td>The number of Twitch streams for the game at a given time.</td>
  </tr>
  <tr>
    <td class="field-column">alternative_names</td>
    <td>An array of alternative names or titles for the game.</td>
  </tr>
  <tr>
    <td class="field-column">parent_achievements_count</td>
    <td>The number of achievements in the parent game of a DLC or special edition.</td>
  </tr>
  <tr>
    <td class="field-column">additions_count</td>
    <td>The number of additions like DLCs or special editions for the game.</td>
  </tr>
  <tr>
    <td class="field-column">reddit_logo</td>
    <td>The URL of the subreddit's logo image.</td>
  </tr>
  <tr>
    <td class="field-column">metacritic_platforms</td>
    <td>An array of objects, each containing the Metacritic score for a specific platform.</td>
  </tr>
  <tr>
    <td class="field-column">screenshots_count</td>
    <td>The total number of screenshots available for the game.</td>
  </tr>
  <tr>
    <td class="field-column">parent_platforms</td>
    <td>An array of parent platform objects (e.g., 'PC', 'PlayStation') to which the specific platforms belong.</td>
  </tr>
  <tr>
    <td class="field-column">game_series_count</td>
    <td>The number of games belonging to the same series.</td>
  </tr>
</table>