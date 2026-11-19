# Frontend mockups

Four screens of the ACTS frontend (Astronaut Career Tracking System), as designed. They show one
view, the career record of one person, in each state it can be in.

The live mockup, where the states can be switched and played:
[Stargate ACTS UI mockup](https://claude.ai/artifact/Y4YyiTC8m61tH6BhWrxjbf). The link is private to
its owner until it is shared.

## What every screen has

- **People**, on the left: everyone on file, with rank and current duty title. Typing narrows the
  list. **Look up** asks for one exact name.
- **Three steps**, at the top of the record. Each one shows whether it has run and how it ended.

| Step | What it does | Where it comes from |
|---|---|---|
| Find person | asks for the person by name | `GET /Person/{name}`, {cs:meth}`PersonController.GetPersonByName` |
| Load duties | asks for the person's duties | `GET /AstronautDuty/{name}`, {cs:meth}`AstronautDutyController.GetAstronautDutiesByName` |
| Check record | compares the dates of the duties with each other | done in the browser, no request |

The list of people comes from `GET /Person`, {cs:meth}`PersonController.GetPeople`. All routes are
on the [HTTP endpoints](../http/index.md) page, and [Paths through the code](paths) shows
what each one does on the server.

## Career record

All three steps passed. The header shows the four values of {cs:type}`AstronautDetail`: rank, duty
title, career start and career end. The career line draws rank over time, one step for every
change of duty. The table lists every {cs:type}`AstronautDuty`, newest first; the current one has
no end date.

```{image} mockups/career-record.png
:alt: The career record of Mara Lindqvist: all three steps passed, a career line from CPT to COL, and a duty history of five rows.
:class: mockup
```

## Loading

The person is found and the duties are being requested. The header is already filled in, the
career line and the table show placeholders, and **Refresh** is off until the answer arrives.

```{image} mockups/loading.png
:alt: The same record while the duties load: the second step shows a spinner, and grey bars stand where the table will be.
:class: mockup
```

## Not found

No person has the name that was looked up. The first step failed and the other two did not run.
The screen says that names must match exactly, offers the closest name on file, and lets the name
be edited.

```{image} mockups/not-found.png
:alt: A lookup of "Mara Lindquist" finds nobody; the screen offers the closest name on file, Mara Lindqvist.
:class: mockup
```

## Request failed

The person is found, but the request for the duties was answered with an error (500). The header
stays, the error box says what failed and that the record was not changed, gives a reference for
support, and offers **Try again**.

```{image} mockups/request-failed.png
:alt: The record with an error box in place of the duty history: "Duty history didn't load", with a Try again button.
:class: mockup
```
