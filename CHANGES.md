# Changes

For every flaw: the request that shows it, what the code as received answered ("before"), what it answers now ("after"), the fix, and the test that guards it. All tests are in `StargateAPI.Tests`.

## Task 1: generate the database

`dotnet ef database update` (in `api`) creates `starbase.db`. Three migrations run: the original `InitialCreate`, then `AddPersonNameUniqueIndex` and `AddProcessLog` from this work.

- Before, with no database: `GET /Person` answered 500 `SQLite Error 1: 'no such table: Person'.`
- After, with no database: 500 `An unexpected error occurred.` The details go to the console log, not to the caller.

## Task 2: enforce the rules

### Rule 1: a person is uniquely identified by their name

- Flaw: the check for an existing name (`CreatePersonPreProcessor`) was written but never registered in `Program.cs`, and the database had no unique index on the name.
- Request: `POST /Person` with `"John Doe"`, twice. Before: 200 both times, ids 1 and 2. After: the second answers 409 `A person with this name already exists.`
- Fix: register the pre-processor; a unique index on `Person.Name`; names compare without regard to upper and lower case (`john doe` is `John Doe`).
- Tests: `Adding_the_same_name_twice_is_refused`, `Names_that_differ_only_by_case_are_the_same_person`, `The_database_itself_refuses_a_duplicate_name`.

### Rules 3, 4 and 5: one current duty, with no end date; the previous duty ends the day before

- Flaw 1: a duty that starts before the current one was accepted. The current duty then got an end date before its own start date, and the person was left with two duties without an end date.
- Request: Jane has `Commander` from 2024-06-01; `POST /AstronautDuty` with `Trainer` from 2023-01-01. Before: 200. After: 400 `A new duty must start after the current duty's start date.`
- Flaw 2: the duplicate check looked at all people, so two people could not start the same duty on the same day.
- Request: Sam gets `Pilot` from 2024-01-15, the same title and day as Jane. Before: refused. After: 200; the same duty twice for one person answers 409.
- Fix: the duplicate check is per person; a new duty must start after the current one; the duty that gets closed is the person's open duty.
- Tests: `A_back_dated_duty_is_refused`, `A_duty_starting_on_the_same_day_as_the_current_one_is_refused`, `Two_people_can_start_the_same_duty_on_the_same_day`, `The_same_duty_twice_is_refused`, `Each_person_has_exactly_one_open_duty`, `The_duty_that_gets_closed_is_the_open_one`.

### Rule 6: a person is retired when the duty title is RETIRED

- Flaw: only the exact text `RETIRED` counted, and it was written out in two places.
- Request: `POST /AstronautDuty` with the title `retired`. Before: stored as `retired`, no career end date. After: stored as `RETIRED`, with a career end date.
- Fix: one constant, `AstronautDuty.RetiredDutyTitle`, compared without regard to case. A duty after retirement is accepted and clears the career end date.
- Tests: `Retired_in_lower_case_counts_as_retired`, `A_duty_after_retirement_clears_the_career_end_date`.

### Rule 7: the career end date is one day before the retired duty start date

- Flaw: when RETIRED was a person's first duty, the career end date was the start date itself, not the day before.
- Request: a person's first duty is `RETIRED` from 2025-06-01, then `GET /Person/{name}`. Before: `careerEndDate` 2025-06-01. After: 2025-05-31.
- Fix: both branches of the handler now use the day before.
- Tests: `Retiring_as_the_first_duty_ends_the_career_the_day_before`, `Retiring_after_a_duty_ends_the_career_the_day_before`.

## Task 3: defensive coding

### Values were pasted into the SQL text

- Request 1: `GET /Person/' OR 1=1 --`. Before: 200 with John Doe, a different person. After: 404 when nobody has that name; the person with exactly that name when somebody does.
- Request 2: add `Miles O'Brien`, then `GET /Person/Miles O'Brien`. Before: 500 `SQLite Error 1: 'near "Brien": syntax error'.` After: 200 with the person.
- Fix: every query passes its values as parameters (`@Name`, `@PersonId`).
- Tests: `Sql_in_a_name_is_treated_as_text`, `A_name_with_an_apostrophe_can_be_read_back`.

### Errors were handled in four copies, and one endpoint had none

- Flaw: four controller actions had the same `try/catch`, which sent the exception's own message with status 500. `POST /AstronautDuty` had none.
- Request: `POST /AstronautDuty` for a person that does not exist. Before: the raw exception text with its stack trace (`Microsoft.AspNetCore.Http.BadHttpRequestException: Bad Request at ...`). After: 404 `{"success":false,"message":"Person not found.","responseCode":404}`
- Fix: one exception handler (`ApiExceptionHandler`) turns every exception into the usual response. A refused request keeps its own message and status code: 404 for an unknown person, 409 for a duplicate, 400 for a missing value. Anything else is a 500 with a general message.
- Tests: `An_unknown_person_returns_404`, `A_duty_for_an_unknown_person_returns_404`, `A_repeated_duty_returns_409_and_a_back_dated_duty_returns_400`, `An_unexpected_error_returns_500_without_internal_details`.

### Missing values and unknown people

- `POST /Person` with `""`. Before: 200, a person without a name. After: 400 `Name is required.`
- `GET /Person/Nobody`. Before: 200 with `"person":null`. After: 404 `Person not found.`
- A duty with a blank rank or title, or without a start date. After: 400 with the name of the missing value.
- Tests: `A_blank_name_is_refused`, `A_blank_rank_or_title_is_refused`, `A_missing_start_date_is_refused`, `Blank_and_missing_values_return_400`, `Asking_for_an_unknown_person_is_refused_with_404`.

### Smaller points

- The database calls in the pre-processors are awaited and pass the cancellation token on; before, they blocked the thread while the database answered.
- The build has 0 warnings; it had 6 (possible null values).

## The API does what the README asks

- `GET /AstronautDuty/{name}` returned the person only, because the controller sent the wrong request (`GetPersonByName`). It now returns the person and the list of duties.
- `PUT /Person/{name}` is new: it changes a person's name (the README asks for "add/update a person by name"). 404 for an unknown person, 409 when the new name is taken, 400 for a blank name.
- Tests: `The_duties_endpoint_returns_the_person_and_the_duties`, `A_person_can_be_renamed_and_keeps_their_duties`, `Renaming_returns_404_409_or_400_when_it_cannot_be_done`.

## Task 4: unit tests

- 53 tests, run with `dotnet test`. They use a real SQLite database held in memory, built by the same migrations as the real one.
- Line coverage: 90.5% of the application code (372 of 411 lines) with the generated migration files left out, 80.1% (823 of 1028) with them counted.

## Task 5: process logging

- New table `ProcessLog`. One row for every request that reaches the application code: the time (UTC), the level (`Information` or `Error`), the name of the request, the message, and the exception text for a failure.
- The row is written through its own database context, so a failed request still leaves its row.
- Tests: `A_successful_request_writes_one_log_row`, `A_refused_request_writes_a_log_row_with_the_exception`, `The_log_row_is_saved_when_the_request_fails_half_way_and_the_request_work_is_not`.

## Decisions that could have gone the other way

- A back-dated duty is refused. The other choice is to fit it into the timeline.
- A duty after RETIRED is accepted and re-opens the career. The other choice is to refuse it.
- RETIRED as a first duty is accepted, so the career ends one day before it starts. The other choice is to refuse it.
- Names are compared without regard to case, for the letters A to Z only (SQLite `NOCASE`).

## Not done

- The user interface.
- Authentication and paging.
- Requests that ASP.NET Core refuses before the application code runs (a body that is not valid JSON, a duty without `rank` or `dutyTitle`) keep the framework's own 400 format, and are not in the log table.
